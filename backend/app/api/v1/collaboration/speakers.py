"""
SPEC-SPEAKER-001: 화자 프로필 관리 API
SPEC-SPEAKER-VOICE-001: 화자 음성 프로파일 분석 API 확장

엔드포인트 (모두 JWT 인증 필요):
- POST   /api/v1/speakers                                 생성
- GET    /api/v1/speakers                                 목록 (task_id, speaker_label 필터링)
- GET    /api/v1/speakers/{id}                            단건 조회
- PATCH  /api/v1/speakers/{id}                            부분 수정 (이름/역할/메모)
- DELETE /api/v1/speakers/{id}                            삭제
- POST   /api/v1/speakers/{id}/analyze-samples            오디오 샘플 분석 후 프로파일 누적
- POST   /api/v1/speakers/{id}/voice-profile              사전 분석 결과로 프로파일 초기화/누적
- GET    /api/v1/speakers/{id}/voice-characteristics      누적 음성 특성 조회
"""

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_current_user, get_db_session
from backend.db.auth_models import User
from backend.schemas.speaker import (
    SpeakerProfileCreate,
    SpeakerProfileListResponse,
    SpeakerProfileResponse,
    SpeakerProfileUpdate,
    VoiceCharacteristics,
    VoiceProfileCreateRequest,
    VoiceSampleAnalyzeResponse,
)
from backend.services.speaker_service import SpeakerService
from backend.services.speaker_voice_service import SpeakerVoiceService

router = APIRouter(prefix="/speakers", tags=["speakers"])


def get_speaker_service() -> SpeakerService:
    """SpeakerService 인스턴스 제공 (FastAPI Depends)"""
    return SpeakerService()


def get_speaker_voice_service() -> SpeakerVoiceService:
    """SpeakerVoiceService 인스턴스 제공 (FastAPI Depends)"""
    return SpeakerVoiceService()


@router.post(
    "",
    response_model=SpeakerProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_speaker(
    payload: SpeakerProfileCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerService = Depends(get_speaker_service),
    voice_svc: SpeakerVoiceService = Depends(get_speaker_voice_service),
) -> SpeakerProfileResponse:
    """REQ-SPEAKER-001: 화자 프로필 생성."""
    profile = await svc.create(db, user.id, payload)
    if payload.enrollment_task_id:
        await voice_svc.enroll_from_task(
            db,
            profile.id,
            user.id,
            source_task_id=payload.enrollment_task_id,
            source_speaker_label=payload.speaker_label,
        )
    return SpeakerProfileResponse.model_validate(profile)


@router.get("", response_model=SpeakerProfileListResponse)
async def list_speakers(
    task_id: str | None = Query(
        default=None,
        max_length=255,
        description="특정 회의록의 화자 프로필만 조회 (전역 프로필 포함)",
    ),
    speaker_label: str | None = Query(
        default=None,
        max_length=50,
        description="특정 화자 레이블만 조회 (예: SPEAKER_00)",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerService = Depends(get_speaker_service),
) -> SpeakerProfileListResponse:
    """REQ-SPEAKER-002: 화자 프로필 목록. task_id 지정 시 해당 회의록 + 전역 프로필 반환."""
    offset = (page - 1) * page_size
    items, total = await svc.list_for_user(
        session=db,
        user_id=user.id,
        task_id=task_id,
        speaker_label=speaker_label,
        limit=page_size,
        offset=offset,
    )
    return SpeakerProfileListResponse(
        items=[SpeakerProfileResponse.model_validate(item) for item in items],
        total=total,
    )


@router.get("/{speaker_id}", response_model=SpeakerProfileResponse)
async def get_speaker(
    speaker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerService = Depends(get_speaker_service),
) -> SpeakerProfileResponse:
    profile = await svc.get_by_id(db, speaker_id, user.id)
    return SpeakerProfileResponse.model_validate(profile)


@router.patch("/{speaker_id}", response_model=SpeakerProfileResponse)
async def update_speaker(
    speaker_id: uuid.UUID,
    payload: SpeakerProfileUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerService = Depends(get_speaker_service),
    voice_svc: SpeakerVoiceService = Depends(get_speaker_voice_service),
) -> SpeakerProfileResponse:
    profile = await svc.update(db, speaker_id, user.id, payload)
    if payload.enrollment_task_id:
        await voice_svc.enroll_from_task(
            db,
            profile.id,
            user.id,
            source_task_id=payload.enrollment_task_id,
            source_speaker_label=payload.enrollment_speaker_label or profile.speaker_label,
        )
    return SpeakerProfileResponse.model_validate(profile)


@router.delete("/{speaker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_speaker(
    speaker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerService = Depends(get_speaker_service),
) -> None:
    await svc.delete(db, speaker_id, user.id)


# ---------------------------------------------------------------------------
# SPEC-SPEAKER-VOICE-001: 음성 프로파일 엔드포인트
# ---------------------------------------------------------------------------


@router.post(
    "/{speaker_id}/analyze-samples",
    response_model=VoiceSampleAnalyzeResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_speaker_sample(
    speaker_id: uuid.UUID,
    file: UploadFile = File(..., description="화자 음성 샘플 오디오"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerService = Depends(get_speaker_service),
    voice_svc: SpeakerVoiceService = Depends(get_speaker_voice_service),
) -> VoiceSampleAnalyzeResponse:
    """REQ-SPEAKER-VOICE-003: 오디오 샘플을 분석해 프로파일에 누적한다."""
    sample, voice = await voice_svc.analyze_upload(
        session=db,
        speaker_id=speaker_id,
        user_id=user.id,
        upload=file,
    )
    return VoiceSampleAnalyzeResponse(
        speaker_profile_id=speaker_id,
        analyzed=sample,
        characteristics=voice_svc.to_characteristics_response(voice),
    )


@router.post(
    "/{speaker_id}/voice-profile",
    response_model=VoiceCharacteristics,
    status_code=status.HTTP_201_CREATED,
)
async def create_or_update_voice_profile(
    speaker_id: uuid.UUID,
    payload: VoiceProfileCreateRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerService = Depends(get_speaker_service),
    voice_svc: SpeakerVoiceService = Depends(get_speaker_voice_service),
) -> VoiceCharacteristics:
    """REQ-SPEAKER-VOICE-001: 사전 분석된 샘플 결과로 프로파일을 생성/누적한다."""
    voice = await voice_svc.create_or_replace_from_samples(
        session=db,
        speaker_id=speaker_id,
        user_id=user.id,
        payload=payload,
    )
    return voice_svc.to_characteristics_response(voice)


@router.get(
    "/{speaker_id}/voice-characteristics",
    response_model=VoiceCharacteristics,
)
async def get_voice_characteristics(
    speaker_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    svc: SpeakerService = Depends(get_speaker_service),
    voice_svc: SpeakerVoiceService = Depends(get_speaker_voice_service),
) -> VoiceCharacteristics:
    """REQ-SPEAKER-VOICE-002: 누적된 음성 특성 조회."""
    voice = await voice_svc.get_characteristics(
        session=db,
        speaker_id=speaker_id,
        user_id=user.id,
    )
    return voice_svc.to_characteristics_response(voice)
