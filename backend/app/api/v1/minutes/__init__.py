"""
Minutes domain package
하위 호환성을 위해 minutes, summary 모듈의 주요 심볼을 노출합니다.
"""

# minutes 모듈의 심볼들을 패키지 레벨로 노출
from backend.app.api.v1.minutes.minutes import (
    router,
    settings,
)

# summary 모듈의 심볼들도 노출 (하위 호환성)
from backend.app.api.v1.minutes.summary import (
    router as summary_router,
)
from backend.app.api.v1.minutes.summary import (
    settings as summary_settings,
)

__all__ = ["router", "settings", "summary_router", "summary_settings"]
