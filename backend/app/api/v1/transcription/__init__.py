"""
Transcription domain package
하위 호환성을 위해 transcription, diarization 모듈의 주요 심볼을 노출합니다.
"""

# transcription 모듈의 심볼들을 패키지 레벨로 노출
# diarization 모듈의 심볼들도 노출 (하위 호환성)
from backend.app.api.v1.transcription.diarization import (
    router as diarization_router,
)
from backend.app.api.v1.transcription.diarization import (
    settings as diarization_settings,
)
from backend.app.api.v1.transcription.transcription import (
    router,
    settings,
)

__all__ = ["router", "settings", "diarization_router", "diarization_settings"]
