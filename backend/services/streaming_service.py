"""
실시간 스트리밍 서비스
"""

import asyncio

from fastapi import WebSocket
from fastapi.websockets import WebSocketState

from backend.core.logger import get_logger

logger = get_logger(__name__)


class StreamingService:
    """실시간 스트리밍 서비스 관리"""

    def __init__(self):
        # 활성 WebSocket 연결 저장
        self.active_connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, meeting_id: str, websocket: WebSocket) -> None:
        """WebSocket 연결 수락"""
        await websocket.accept()

        async with self._lock:
            if meeting_id not in self.active_connections:
                self.active_connections[meeting_id] = set()

            self.active_connections[meeting_id].add(websocket)

        logger.info("WebSocket 연결 수락", meeting_id=meeting_id)

    async def disconnect(self, meeting_id: str, websocket: WebSocket) -> None:
        """WebSocket 연결 해제"""
        async with self._lock:
            if meeting_id in self.active_connections:
                self.active_connections[meeting_id].discard(websocket)

                # 해당 미팅에 더는 연결이 없으면 삭제
                if not self.active_connections[meeting_id]:
                    del self.active_connections[meeting_id]

        logger.info("WebSocket 연결 해제", meeting_id=meeting_id)

    async def broadcast(self, meeting_id: str, message: dict) -> None:
        """미팅 참가자들에게 메시지 브로드캐스트"""
        async with self._lock:
            if meeting_id not in self.active_connections:
                return

            # 연결이 끊어진 소켓 제거
            active_websockets = set()
            for websocket in self.active_connections[meeting_id]:
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_json(message)
                        active_websockets.add(websocket)
                    except Exception as e:
                        logger.warning("WebSocket 메시지 전송 실패", error=str(e))

            # 활성 연결만 유지
            self.active_connections[meeting_id] = active_websockets

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """특정 사용자에게 메시지 전송"""
        # 구현 필요: 사용자별 연결 관리
        pass

    def get_connection_count(self, meeting_id: str) -> int:
        """연결된 클라이언트 수 조회"""
        return len(self.active_connections.get(meeting_id, set()))

    async def broadcast_caption_segment(self, meeting_id: str, segment: dict) -> None:
        """자막 세그먼트 브로드캐스트"""
        message = {
            "type": "caption_segment",
            "data": segment,
            "timestamp": segment.get("start_time")
        }

        await self.broadcast(meeting_id, message)
        logger.debug("자막 세그먼트 브로드캐스트", meeting_id=meeting_id)


# 전역 인스턴스
streaming_service = StreamingService()
