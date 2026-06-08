"""
외부 서비스 통합 API - Slack, Teams, Notion 등 외부 서비스와의 연동 기능

SPEC-INTEGRATION-001: 외부 서비스 연동 관리 API
SPEC-INTEGRATION-002: 웹훅 기반 자동 동기화
SPEC-INTEGRATION-003: 양방향 데이터 동기화
"""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from backend.app.api.dependencies import get_current_user
from backend.core.exceptions import IntegrationError
from backend.db.integration_models import Integration
from backend.schemas.integration import (
    IntegrationRequest,
    IntegrationResponse,
    IntegrationType,
    NotionConfig,
    SlackConfig,
    TeamsConfig,
    WebhookResponse,
)
from backend.services.integration_service import IntegrationService
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


class IntegrationManager:
    """통합 서비스 관리자"""

    def __init__(self):
        self.active_integrations: dict[str, Integration] = {}
        self.webhook_handlers = {
            IntegrationType.SLACK.value: self._handle_slack_webhook,
            IntegrationType.TEAMS.value: self._handle_teams_webhook,
            IntegrationType.NOTION.value: self._handle_notion_webhook,
        }

    async def create_integration(
        self,
        integration_type: IntegrationType,
        config: dict,
        user_id: str
    ) -> Integration:
        """새로운 통합 생성"""
        integration = Integration(
            integration_type=integration_type.value,
            config=config,
            user_id=user_id,
            status="active",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        self.active_integrations[integration.integration_id] = integration  # type: ignore[index]
        logger.info("통합 생성 성공", integration_id=integration.integration_id, type=integration_type.value)

        return integration

    async def handle_webhook(
        self,
        integration_type: IntegrationType,
        payload: dict,
        headers: dict
    ) -> dict:
        """웹훅 처리"""
        handler = self.webhook_handlers.get(integration_type.value)
        if not handler:
            raise IntegrationError(f"지원하지 않는 통합 타입: {integration_type}")

        return await handler(payload, headers)

    async def _handle_slack_webhook(self, payload: dict, headers: dict) -> dict:
        """Slack 웹훅 처리"""
        # Slack 웹훅 처리 로직
        return {
            "status": "success",
            "message": "Slack 웹훅 처리 완료",
            "timestamp": datetime.now().isoformat()
        }

    async def _handle_teams_webhook(self, payload: dict, headers: dict) -> dict:
        """Teams 웹훅 처리"""
        # Teams 웹훅 처리 로직
        return {
            "status": "success",
            "message": "Teams 웹훅 처리 완료",
            "timestamp": datetime.now().isoformat()
        }

    async def _handle_notion_webhook(self, payload: dict, headers: dict) -> dict:
        """Notion 웹훅 처리"""
        # Notion 웹훅 처리 로직
        return {
            "status": "success",
            "message": "Notion 웹훅 처리 완료",
            "timestamp": datetime.now().isoformat()
        }


# 전역 통합 관리자
integration_manager = IntegrationManager()


@router.post("/", response_model=IntegrationResponse)
async def create_integration(
    request: IntegrationRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    integration_service: IntegrationService = Depends(IntegrationService)
):
    """외부 서비스 통합 생성"""
    try:
        # 통합 생성
        integration = await integration_manager.create_integration(
            integration_type=request.integration_type,
            config=request.config,
            user_id=user["user_id"]
        )

        # 유효성 검증 및 테스트
        await integration_service.test_integration(integration)

        # DB 저장
        await integration_service.save_integration(integration)

        return IntegrationResponse(
            integration_id=integration.integration_id,
            integration_type=integration.integration_type,
            status=integration.status,
            created_at=integration.created_at,
            config=integration.config
        )

    except Exception as e:
        logger.error("통합 생성 실패", error=str(e))
        raise HTTPException(status_code=500, detail=f"통합 생성 실패: {str(e)}")


@router.get("/", response_model=list[IntegrationResponse])
async def get_integrations(
    user: dict = Depends(get_current_user),
    integration_service: IntegrationService = Depends(IntegrationService)
):
    """사용자의 통합 목록 조회"""
    try:
        integrations = await integration_service.get_user_integrations(user["user_id"])
        return [
            IntegrationResponse(
                integration_id=integration.integration_id,
                integration_type=integration.integration_type,
                status=integration.status,
                created_at=integration.created_at,
                config=integration.config
            )
            for integration in integrations
        ]
    except Exception as e:
        logger.error("통합 목록 조회 실패", error=str(e))
        raise HTTPException(status_code=500, detail="통합 목록 조회 실패")


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: str,
    user: dict = Depends(get_current_user),
    integration_service: IntegrationService = Depends(IntegrationService)
):
    """특정 통합 상세 정보 조회"""
    try:
        integration = await integration_service.get_integration(integration_id)
        if not integration:
            raise HTTPException(status_code=404, detail="통합을 찾을 수 없습니다")

        if integration.user_id != user["user_id"]:
            raise HTTPException(status_code=403, detail="접근 권한이 없습니다")

        return IntegrationResponse(
            integration_id=integration.integration_id,
            integration_type=integration.integration_type,
            status=integration.status,
            created_at=integration.created_at,
            config=integration.config
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("통합 상세 조회 실패", error=str(e))
        raise HTTPException(status_code=500, detail="통합 상세 조회 실패")


@router.put("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: str,
    request: IntegrationRequest,
    user: dict = Depends(get_current_user),
    integration_service: IntegrationService = Depends(IntegrationService)
):
    """통합 정보 업데이트"""
    try:
        integration = await integration_service.get_integration(integration_id)
        if not integration:
            raise HTTPException(status_code=404, detail="통합을 찾을 수 없습니다")

        if integration.user_id != user["user_id"]:
            raise HTTPException(status_code=403, detail="접근 권한이 없습니다")

        # 업데이트
        integration.config = request.config
        integration.updated_at = datetime.now()

        # 유효성 검증
        await integration_service.test_integration(integration)

        # DB 저장
        await integration_service.save_integration(integration)

        return IntegrationResponse(
            integration_id=integration.integration_id,
            integration_type=integration.integration_type,
            status=integration.status,
            created_at=integration.created_at,
            config=integration.config
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("통합 업데이트 실패", error=str(e))
        raise HTTPException(status_code=500, detail="통합 업데이트 실패")


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: str,
    user: dict = Depends(get_current_user),
    integration_service: IntegrationService = Depends(IntegrationService)
):
    """통합 삭제"""
    try:
        integration = await integration_service.get_integration(integration_id)
        if not integration:
            raise HTTPException(status_code=404, detail="통합을 찾을 수 없습니다")

        if integration.user_id != user["user_id"]:
            raise HTTPException(status_code=403, detail="접근 권한이 없습니다")

        # DB 삭제
        await integration_service.delete_integration(integration_id)

        # 메모리에서도 삭제
        if integration_id in integration_manager.active_integrations:
            del integration_manager.active_integrations[integration_id]

        return {"message": "통합이 삭제되었습니다"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("통합 삭제 실패", error=str(e))
        raise HTTPException(status_code=500, detail="통합 삭제 실패")


@router.post("/slack/test")
async def test_slack_integration(
    config: SlackConfig,
    user: dict = Depends(get_current_user),
    integration_service: IntegrationService = Depends(IntegrationService)
):
    """Slack 통합 테스트"""
    try:
        test_integration = Integration(
            integration_type=IntegrationType.SLACK.value,
            config=config.dict(),
            user_id=user["user_id"],
            status="testing",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        await integration_service.test_integration(test_integration)

        return {"message": "Slack 통합 테스트 성공"}

    except Exception as e:
        logger.error("Slack 통합 테스트 실패", error=str(e))
        raise HTTPException(status_code=500, detail=f"Slack 통합 테스트 실패: {str(e)}")


@router.post("/teams/test")
async def test_teams_integration(
    config: TeamsConfig,
    user: dict = Depends(get_current_user),
    integration_service: IntegrationService = Depends(IntegrationService)
):
    """Teams 통합 테스트"""
    try:
        test_integration = Integration(
            integration_type=IntegrationType.TEAMS.value,
            config=config.dict(),
            user_id=user["user_id"],
            status="testing",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        await integration_service.test_integration(test_integration)

        return {"message": "Teams 통합 테스트 성공"}

    except Exception as e:
        logger.error("Teams 통합 테스트 실패", error=str(e))
        raise HTTPException(status_code=500, detail=f"Teams 통합 테스트 실패: {str(e)}")


@router.post("/notion/test")
async def test_notion_integration(
    config: NotionConfig,
    user: dict = Depends(get_current_user),
    integration_service: IntegrationService = Depends(IntegrationService)
):
    """Notion 통합 테스트"""
    try:
        test_integration = Integration(
            integration_type=IntegrationType.NOTION.value,
            config=config.dict(),
            user_id=user["user_id"],
            status="testing",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        await integration_service.test_integration(test_integration)

        return {"message": "Notion 통합 테스트 성공"}

    except Exception as e:
        logger.error("Notion 통합 테스트 실패", error=str(e))
        raise HTTPException(status_code=500, detail=f"Notion 통합 테스트 실패: {str(e)}")


@router.post("/webhook/{integration_type}", response_model=WebhookResponse)
async def handle_webhook(
    integration_type: IntegrationType,
    payload: dict,
    headers: dict,
    integration_service: IntegrationService = Depends(IntegrationService)
):
    """외부 서비스 웹훅 처리"""
    try:
        # 웹훅 로그 저장
        await integration_service.log_webhook(
            integration_type.value,
            payload,
            headers
        )

        # 웹훅 처리
        result = await integration_manager.handle_webhook(integration_type, payload, headers)

        return WebhookResponse(
            status="success",
            message="웹훅 처리 완료",
            data=result,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error("웹훅 처리 실패", error=str(e))
        raise HTTPException(status_code=500, detail=f"웹훅 처리 실패: {str(e)}")


@router.get("/webhook/logs", response_model=list[dict])
async def get_webhook_logs(
    integration_type: IntegrationType | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    integration_service: IntegrationService = Depends(IntegrationService)
):
    """웹훅 로그 조회"""
    try:
        logs = await integration_service.get_webhook_logs(
            integration_type.value if integration_type else None,
            limit
        )
        return logs

    except Exception as e:
        logger.error("웹훅 로그 조회 실패", error=str(e))
        raise HTTPException(status_code=500, detail="웹훅 로그 조회 실패")
