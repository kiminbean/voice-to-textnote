"""
자막 생성 서비스
"""

import asyncio
from datetime import datetime

from backend.core.logger import get_logger
from backend.db.caption_models import CaptionSegment, CaptionSession, CaptionTask
from backend.ml.stt_engine import WhisperEngine
from backend.schemas.caption import CaptionFormat, CaptionStatus

logger = get_logger(__name__)


class CaptionService:
    """자막 생성 서비스"""

    def __init__(self):
        self.whisper_engine = WhisperEngine.get_instance()
        self.active_tasks: dict[str, asyncio.Task] = {}

    async def save_session(self, session: CaptionSession) -> None:
        """세션 저장"""
        # DB 저장 로직
        pass

    async def get_session(self, session_id: str) -> CaptionSession | None:
        """세션 조회"""
        # DB 조회 로직
        pass

    async def delete_session(self, session_id: str) -> None:
        """세션 삭제"""
        # DB 삭제 로직
        pass

    async def create_caption_task(
        self,
        meeting_id: str,
        audio_url: str | None,
        user_id: str,
        language: str = "ko",
        format: CaptionFormat = CaptionFormat.VTT
    ) -> str:
        """자막 생성 작업 생성"""
        task_id = f"caption_{meeting_id}_{datetime.now().timestamp()}"

        # 작업 생성
        task = CaptionTask(
            task_id=task_id,
            meeting_id=meeting_id,
            user_id=user_id,
            audio_url=audio_url,
            language=language,
            format=format.value,
            status=CaptionStatus.PENDING.value
        )

        # 비동기 작업 시작
        asyncio_task = asyncio.create_task(self._process_caption_task(task))
        self.active_tasks[task_id] = asyncio_task

        logger.info("자막 생성 작업 생성", task_id=task_id, meeting_id=meeting_id)
        return task_id

    async def _process_caption_task(self, task: CaptionTask) -> None:
        """자막 처리 비동기 작업"""
        try:
            # 상태 업데이트: PROCESSING
            task.status = CaptionStatus.PROCESSING.value  # type: ignore[assignment]
            task.progress = 10  # type: ignore[assignment]

            # 실제 구현에서는 오디오 URL에서 파일 다운로드 및 처리
            # 여기서는 더미 데이터로 처리

            # STT 처리
            task.progress = 30  # type: ignore[assignment]
            await asyncio.sleep(1)  # 가상 처리 시간

            # 음성 인식 결과 생성
            segments = [
                CaptionSegment(
                    index=0,
                    text="첫 번째 자막 텍스트 예시입니다.",
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    confidence=0.95,
                    speaker_id="speaker_1"
                ),
                CaptionSegment(
                    index=1,
                    text="두 번째 자막 텍스트 예시입니다.",
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    confidence=0.92,
                    speaker_id="speaker_2"
                )
            ]

            task.progress = 80  # type: ignore[assignment]

            # 결과 저장
            task.result_data = {  # type: ignore[assignment]
                "segments": [seg.dict() for seg in segments],
                "total_duration": 120.5,
                "language": task.language
            }

            task.status = CaptionStatus.COMPLETED.value  # type: ignore[assignment]
            task.progress = 100  # type: ignore[assignment]
            task.completed_at = datetime.now()  # type: ignore[assignment]

            logger.info("자막 처리 완료", task_id=task.task_id)

        except Exception as e:
            logger.error("자막 처리 실패", task_id=task.task_id, error=str(e))
            task.status = CaptionStatus.FAILED.value  # type: ignore[assignment]
            task.error_message = str(e)  # type: ignore[assignment]

    async def get_caption(self, task_id: str) -> dict | None:
        """자막 데이터 조회"""
        # DB 조회 로직
        pass

    def generate_vtt(self, caption_data: dict) -> str:
        """WebVTT 형식 자막 생성"""
        if not caption_data or "segments" not in caption_data:
            return ""

        vtt_content = "WEBVTT\n\n"

        for i, segment in enumerate(caption_data["segments"]):
            start_time = self._format_time(segment.get("start_time", 0))
            end_time = self._format_time(segment.get("end_time", 0))
            text = segment.get("text", "")

            vtt_content += f"{i + 1}\n"
            vtt_content += f"{start_time} --> {end_time}\n"
            vtt_content += f"{text}\n\n"

        return vtt_content

    def generate_srt(self, caption_data: dict) -> str:
        """SRT 형식 자막 생성"""
        if not caption_data or "segments" not in caption_data:
            return ""

        srt_content = ""

        for i, segment in enumerate(caption_data["segments"]):
            start_time = self._format_srt_time(segment.get("start_time", 0))
            end_time = self._format_srt_time(segment.get("end_time", 0))
            text = segment.get("text", "")

            srt_content += f"{i + 1}\n"
            srt_content += f"{start_time} --> {end_time}\n"
            srt_content += f"{text}\n\n"

        return srt_content

    def _format_time(self, timestamp: float | datetime) -> str:
        """VTT 시간 형식으로 변환"""
        if isinstance(timestamp, datetime):
            total_seconds = timestamp.timestamp()
        else:
            total_seconds = timestamp

        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    def _format_srt_time(self, timestamp: float | datetime) -> str:
        """SRT 시간 형식으로 변환"""
        if isinstance(timestamp, datetime):
            total_seconds = timestamp.timestamp()
        else:
            total_seconds = timestamp

        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
