"""
AC-DI-009 ~ AC-DI-014: Dependency Injection 엔진 테스트

WhisperEngine와 DiarizationEngine이 클래스 레벨 싱글톤이 아닌
FastAPI app.state에 저장되어 의존성 주입으로 사용되는지 검증합니다.
"""

from unittest.mock import MagicMock


class TestEngineDI:
    """AC-DI-009 to AC-DI-014"""

    def test_whisper_has_deprecated_singleton_shim(self):
        """AC-DI-014: get_instance()는 deprecated shim으로 존재 (Phase 5에서 제거)"""
        from backend.ml.stt_engine import WhisperEngine

        # deprecated shim 존재 확인 (Phase 5에서 제거 예정)
        assert hasattr(WhisperEngine, "get_instance"), "Shim should exist for backward compat"

        # 직접 인스턴스화 가능해야 함 (DI 패턴)
        engine = WhisperEngine()
        assert engine is not None

    def test_diarization_has_deprecated_singleton_shim(self):
        """AC-DI-014: get_instance()는 deprecated shim으로 존재 (Phase 5에서 제거)"""
        from backend.ml.diarization_engine import DiarizationEngine

        # deprecated shim 존재 확인 (Phase 5에서 제거 예정)
        assert hasattr(DiarizationEngine, "get_instance"), "Shim should exist for backward compat"

        # 직접 인스턴스화 가능해야 함 (DI 패턴)
        engine = DiarizationEngine()
        assert engine is not None

    def test_engine_constructible(self):
        """AC-DI-014: 엔진 클래스를 직접 인스턴스화 가능"""
        from backend.ml.diarization_engine import DiarizationEngine
        from backend.ml.stt_engine import WhisperEngine

        # 단순 인스턴스화만 가능하면 됨
        w = WhisperEngine()
        d = DiarizationEngine()
        assert w is not None
        assert d is not None

    def test_get_whisper_from_app_state(self):
        """AC-DI-010: get_whisper_engine가 app.state.whisper_engine 반환"""
        from backend.app.dependencies import get_whisper_engine

        mock_request = MagicMock()
        mock_engine = MagicMock()

        # Request.app.state.whisper_engine 모의 설정
        mock_request.app.state.whisper_engine = mock_engine

        result = get_whisper_engine(mock_request)
        assert result is mock_engine, "Should return engine from app.state"

    def test_get_diarization_from_app_state(self):
        """AC-DI-013: get_diarization_engine가 app.state.diarization_engine 반환"""
        from backend.app.dependencies import get_diarization_engine

        mock_request = MagicMock()
        mock_engine = MagicMock()

        # Request.app.state.diarization_engine 모의 설정
        mock_request.app.state.diarization_engine = mock_engine

        result = get_diarization_engine(mock_request)
        assert result is mock_engine, "Should return engine from app.state"

    def test_lazy_load_preserved(self):
        """AC-DI-011: load() 메서드와 인스턴스 레벨 self._lock 보존"""
        from backend.ml.diarization_engine import DiarizationEngine
        from backend.ml.stt_engine import WhisperEngine

        w_engine = WhisperEngine()
        d_engine = DiarizationEngine()

        # load() 메서드 존재
        assert hasattr(w_engine, "load"), "WhisperEngine should have load method"
        assert hasattr(d_engine, "load"), "DiarizationEngine should have load method"

        # 인스턴스 레벨 _lock 존재 (스레드 안전 lazy load용)
        assert hasattr(w_engine, "_lock"), "WhisperEngine should have instance-level _lock"
        assert hasattr(d_engine, "_lock"), "DiarizationEngine should have instance-level _lock"

    def test_worker_registry_module_exists(self):
        """AC-DI-012: Celery worker용 engine_registry 모듈 존재"""
        from backend.workers import engine_registry

        # 모듈 로드 가능성 검증
        assert hasattr(engine_registry, "get_worker_whisper_engine")
        assert hasattr(engine_registry, "get_worker_diarization_engine")

    def test_worker_whisper_singleton_thread_safe(self):
        """AC-DI-012: Celery worker 싱글톤 스레드 안전성"""
        import threading

        from backend.workers.engine_registry import get_worker_whisper_engine

        results = []
        lock = threading.Lock()

        def _create_and_check():
            engine = get_worker_whisper_engine()
            with lock:
                results.append(id(engine))

        # 여러 스레드에서 동시 호출
        threads = [threading.Thread(target=_create_and_check) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 모든 스레드가 동일한 인스턴스 ID를 가져야 함 (싱글톤)
        assert len(set(results)) == 1, "All threads should get the same instance"
        assert results[0] is not None, "Instance should not be None"

    def test_worker_diarization_singleton_thread_safe(self):
        """AC-DI-012: Celery worker 싱글톤 스레드 안전성"""
        import threading

        from backend.workers.engine_registry import get_worker_diarization_engine

        results = []
        lock = threading.Lock()

        def _create_and_check():
            engine = get_worker_diarization_engine()
            with lock:
                results.append(id(engine))

        # 여러 스레드에서 동시 호출
        threads = [threading.Thread(target=_create_and_check) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 모든 스레드가 동일한 인스턴스 ID를 가져야 함 (싱글톤)
        assert len(set(results)) == 1, "All threads should get the same instance"
        assert results[0] is not None, "Instance should not be None"
