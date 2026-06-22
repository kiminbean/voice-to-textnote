"""
SPEC-QA-001: 회의 Q&A 서비스 — OpenAI 기반

회의 트랜스크립트를 컨텍스트로 사용하여 자연어 질문에 답변한다.
"""

import json
import uuid
from typing import cast

import redis.asyncio as aioredis
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.schemas.qa import (
    CrossMeetingAskResponse,
    CrossMeetingSource,
    MeetingAskResponse,
    QAHistoryItem,
    QAHistoryResponse,
    QASource,
)
from backend.services.search_service import SearchService
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Redis 키 프리픽스
_QA_KEY_PREFIX = "qa:history:"


class QAService:
    """회의 Q&A 서비스"""

    def _get_client(self) -> OpenAI:
        return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    def _build_prompt(self, question: str, transcript: str) -> str:
        return f"""다음은 회의 녹취록입니다. 이 회의 내용을 바탕으로 질문에 답변해 주세요.

## 회의 대화 내용
{transcript}

## 질문
{question}

## 지시사항
- 회의 내용을 기반으로 정확하게 답변하세요.
- 회의에서 언급되지 않은 내용은 "회의에서 언급되지 않았습니다"라고 답변하세요.
- 답변은 한국어로 작성하세요.
- 출처가 되는 발화 내용을 sources에 포함하세요."""

    def _format_transcript(self, minutes_data: dict) -> str:
        """MinutesResponse dict를 LLM용 텍스트로 변환"""
        segments = minutes_data.get("segments", [])
        if not segments:
            return minutes_data.get("raw_text", "")

        lines = []
        for i, seg in enumerate(segments):
            speaker = seg.get("speaker", "알 수 없음")
            text = seg.get("text", "")
            lines.append(f"[{i}] {speaker}: {text}")
        return "\n".join(lines)

    async def ask(
        self,
        task_id: str,
        question: str,
        redis_client: aioredis.Redis,
        thread_id: str | None = None,
    ) -> MeetingAskResponse:
        """질문에 대한 답변을 생성한다."""
        # 1. 트랜스크립트 조회
        result_key = f"task:min:result:{task_id}"
        raw = await redis_client.get(result_key)
        if raw is None:
            raise ValueError("회의록을 찾을 수 없습니다. 처리가 완료되었는지 확인하세요.")

        minutes_data = json.loads(cast(str | bytes | bytearray, raw))
        transcript = self._format_transcript(minutes_data)

        if not transcript.strip():
            raise ValueError("회의록 내용이 비어 있습니다.")

        # 2. 대화 이력 조회 (thread_id가 있으면 이전 Q&A를 컨텍스트에 포함)
        if thread_id is None:
            thread_id = str(uuid.uuid4())

        messages = await self._build_messages(
            redis_client, task_id, thread_id, question, transcript
        )

        # 3. OpenAI API 호출
        client = self._get_client()
        logger.info("Q&A API 호출", task_id=task_id, question_len=len(question))

        response = client.chat.completions.create(
            model=settings.summary_model,
            max_tokens=1500,
            messages=messages,
        )

        answer_text = response.choices[0].message.content or ""

        # 4. 출처 세그먼트 추출 (간단한 키워드 매칭)
        sources = self._extract_sources(question, answer_text, minutes_data)

        # 5. 이력 저장
        history_item = QAHistoryItem(
            question=question,
            answer=answer_text,
            sources=sources,
            created_at=__import__("datetime").datetime.now().isoformat(),
        )
        await self._save_history(redis_client, task_id, thread_id, history_item)

        return MeetingAskResponse(
            answer=answer_text,
            sources=sources,
            thread_id=thread_id,
        )

    async def ask_across_meetings(
        self,
        session: AsyncSession,
        question: str,
        limit: int = 5,
        search_service: SearchService | None = None,
    ) -> CrossMeetingAskResponse:
        """여러 회의/요약에서 질문과 관련된 근거를 찾고 요약 답변을 반환합니다."""
        search_service = search_service or SearchService()
        contexts = await search_service.find_answer_contexts(
            session=session,
            question=question,
            limit=limit,
        )
        if not contexts.items:
            raise ValueError("질문과 관련된 회의 근거를 찾을 수 없습니다")

        sources = [
            CrossMeetingSource(
                task_id=item.task_id,
                task_type=item.task_type,
                snippet=item.snippet,
                created_at=item.created_at.isoformat(),
                completed_at=item.completed_at.isoformat() if item.completed_at else None,
            )
            for item in contexts.items
        ]
        answer = self._synthesize_cross_meeting_answer(question, sources)
        return CrossMeetingAskResponse(
            answer=answer,
            sources=sources,
            query=contexts.query,
            total=contexts.total,
        )

    def _synthesize_cross_meeting_answer(
        self,
        question: str,
        sources: list[CrossMeetingSource],
    ) -> str:
        """검색된 근거만 사용해 cross-meeting 답변을 합성합니다."""
        fallback = self._build_cross_meeting_answer(question, sources)
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=settings.summary_model,
                max_tokens=900,
                messages=self._build_cross_meeting_messages(question, sources),
            )
            answer = (response.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning("Cross-meeting Q&A 합성 실패", question=question, error=str(e))
            return fallback

        return answer or fallback

    def _build_cross_meeting_messages(
        self,
        question: str,
        sources: list[CrossMeetingSource],
    ) -> list[ChatCompletionMessageParam]:
        """Cross-meeting Q&A 합성용 메시지를 구성합니다."""
        source_blocks = []
        for index, source in enumerate(sources[:8], start=1):
            source_blocks.append(
                "\n".join(
                    [
                        f"[{index}] task_id={source.task_id}",
                        f"type={source.task_type}",
                        f"created_at={source.created_at}",
                        f"snippet={source.snippet}",
                    ]
                )
            )

        joined_sources = "\n\n".join(source_blocks)
        return [
            {
                "role": "system",
                "content": (
                    "당신은 여러 회의록과 요약을 분석하는 AI 어시스턴트입니다. "
                    "반드시 제공된 근거 snippets 안의 정보만 사용하세요. "
                    "근거에 없는 내용은 추정하지 말고 '검색된 근거에서 확인되지 않았습니다'라고 답하세요. "
                    "답변은 한국어로 간결하게 작성하고, 관련 task_id를 문장 안에 포함하세요."
                ),
            },
            {
                "role": "user",
                "content": f"질문: {question}\n\n검색된 근거:\n{joined_sources}",
            },
        ]

    def _build_cross_meeting_answer(
        self,
        question: str,
        sources: list[CrossMeetingSource],
    ) -> str:
        """검색 근거만 사용해 안전한 1차 답변을 구성합니다."""
        source_lines = [
            f"- {source.task_id} ({source.task_type}): {source.snippet}" for source in sources[:5]
        ]
        joined_sources = "\n".join(source_lines)
        return (
            f"질문 '{question}'와 관련된 회의 근거 {len(sources)}건을 찾았습니다. "
            "아래 근거를 기준으로 확인하세요.\n"
            f"{joined_sources}"
        )

    async def _build_messages(
        self,
        redis_client: aioredis.Redis,
        task_id: str,
        thread_id: str,
        question: str,
        transcript: str,
    ) -> list[ChatCompletionMessageParam]:
        """대화 이력을 포함한 메시지 목록 생성"""
        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "당신은 회의 내용을 분석하는 AI 어시스턴트입니다. 주어진 회의록을 바탕으로 정확하게 답변하세요.",
            }
        ]

        # 이전 대화 이력 로드
        history = await self._load_history(redis_client, task_id, thread_id)
        for item in history[-6:]:  # 최근 6개만 컨텍스트에 포함
            messages.append({"role": "user", "content": item.question})
            messages.append({"role": "assistant", "content": item.answer})

        # 현재 질문 (트랜스크립트 포함)
        messages.append(
            {
                "role": "user",
                "content": self._build_prompt(question, transcript),
            }
        )

        return messages

    def _extract_sources(self, question: str, answer: str, minutes_data: dict) -> list[QASource]:
        """답변과 관련된 트랜스크립트 세그먼트를 출처로 추출"""
        segments = minutes_data.get("segments", [])
        if not segments:
            return []

        # 답변에서 언급된 키워드가 포함된 세그먼트를 출처로 선택
        sources = []
        answer_words = set(answer.split())
        for i, seg in enumerate(segments):
            text = seg.get("text", "")
            # 답변 단어와 30% 이상 겹치는 세그먼트를 관련성 높음으로 판단
            seg_words = set(text.split())
            overlap = len(answer_words & seg_words)
            if overlap >= max(3, len(seg_words) * 0.3):
                sources.append(
                    QASource(
                        segment_index=i,
                        speaker=seg.get("speaker"),
                        text=text[:200],
                    )
                )
            if len(sources) >= 5:
                break

        return sources

    async def _save_history(
        self,
        redis_client: aioredis.Redis,
        task_id: str,
        thread_id: str,
        item: QAHistoryItem,
    ) -> None:
        """Q&A 이력을 Redis에 저장"""
        key = f"{_QA_KEY_PREFIX}{task_id}:{thread_id}"
        raw = await redis_client.get(key)
        history = json.loads(cast(str | bytes | bytearray, raw)) if raw else []
        history.append(item.model_dump())
        # 24시간 TTL
        await redis_client.set(key, json.dumps(history, ensure_ascii=False), ex=86400)

    async def _load_history(
        self,
        redis_client: aioredis.Redis,
        task_id: str,
        thread_id: str,
    ) -> list[QAHistoryItem]:
        """Q&A 이력을 Redis에서 로드"""
        key = f"{_QA_KEY_PREFIX}{task_id}:{thread_id}"
        raw = await redis_client.get(key)
        if raw is None:
            return []
        history = json.loads(cast(str | bytes | bytearray, raw))
        return [QAHistoryItem(**item) for item in history]

    async def get_history(
        self,
        task_id: str,
        redis_client: aioredis.Redis,
    ) -> QAHistoryResponse:
        """task_id의 모든 Q&A 이력 조회 (모든 thread)"""
        # scan으로 모든 thread의 이력 조회
        pattern = f"{_QA_KEY_PREFIX}{task_id}:*"
        all_items: list[QAHistoryItem] = []
        async for key in redis_client.scan_iter(match=pattern):
            raw = await redis_client.get(key)
            if raw:
                items = json.loads(cast(str | bytes | bytearray, raw))
                all_items.extend(QAHistoryItem(**item) for item in items)

        # 시간순 정렬
        all_items.sort(key=lambda x: x.created_at)
        return QAHistoryResponse(items=all_items, total=len(all_items))
