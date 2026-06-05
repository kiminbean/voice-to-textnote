"""
E2E 파이프라인 통합 테스트
SPEC-E2E-001: STT → DIA → MIN → SUM 전체 파이프라인 검증

REQ-E2E-004: STT → DIA 연결 검증
REQ-E2E-005: DIA → MIN 연결 검증
REQ-E2E-006: MIN → SUM 연결 검증
REQ-E2E-007: 전체 4단계 파이프라인 순차 검증
REQ-E2E-008: 존재하지 않는 task_id 에러 처리
REQ-E2E-009: 각 단계 상태 엔드포인트 검증
REQ-E2E-010: 각 단계 삭제 엔드포인트 검증
REQ-E2E-011: DIA 동시 처리 한도 429 검증
REQ-E2E-012: MIN/SUM 동시 처리 한도 429 검증
"""

from fastapi.testclient import TestClient

from backend.tests.e2e.conftest import (
    MOCK_DIA_RESULT,
    MOCK_MIN_RESULT,
    MOCK_STT_RESULT,
    MOCK_SUM_RESULT,
    InMemoryRedis,
    inject_result,
    make_test_wav,
)

# ---------------------------------------------------------------------------
# REQ-E2E-004: STT → DIA 파이프라인 연결 검증
# ---------------------------------------------------------------------------


class TestSTTToDIAPipeline:
    """STT → DIA 파이프라인 단계 검증 (REQ-E2E-004)"""

    def test_stt_upload_returns_task_id(
        self,
        e2e_client: TestClient,
    ) -> None:
        """
        STT 업로드 요청 시 201 상태코드와 task_id 반환 검증
        Celery delay mock으로 실제 처리 없이 작업 등록 확인
        """
        # WAV 파일 생성
        wav_bytes = make_test_wav(duration_seconds=1)

        response = e2e_client.post(
            "/api/v1/transcriptions",
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
            data={"language": "ko"},
        )

        assert response.status_code == 201
        data = response.json()
        # task_id 필드 존재 확인
        assert "task_id" in data
        assert data["task_id"] is not None
        # 상태 URL 포함 확인
        assert "status_url" in data
        assert "result_url" in data

    def test_dia_request_with_stt_task_id(
        self,
        e2e_client: TestClient,
        e2e_redis: InMemoryRedis,
    ) -> None:
        """
        STT 결과를 Redis에 주입한 후 DIA 요청 시 202 응답 검증
        stt_task_id 연결로 파이프라인 체이닝 확인
        """
        import asyncio

        stt_task_id = "11111111-1111-1111-1111-111111111111"

        # STT 결과를 Redis에 직접 주입 (Celery 워커 시뮬레이션)
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:status:{stt_task_id}",
                result_key=f"task:result:{stt_task_id}",
                task_id=stt_task_id,
                result_dict={**MOCK_STT_RESULT, "task_id": stt_task_id},
            )
        )

        # DIA 요청 (stt_task_id로 연결)
        response = e2e_client.post(
            "/api/v1/diarizations",
            json={"stt_task_id": stt_task_id},
        )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        # stt_task_id가 응답에 포함되어야 함
        assert data["stt_task_id"] == stt_task_id

    def test_dia_result_has_speaker_ids(
        self,
        e2e_client: TestClient,
        e2e_redis: InMemoryRedis,
    ) -> None:
        """
        DIA 결과 조회 시 화자 ID가 포함된 세그먼트 반환 검증
        """
        import asyncio

        dia_task_id = "22222222-2222-2222-2222-222222222222"
        stt_task_id = "11111111-1111-1111-1111-111111111111"

        # DIA 결과를 Redis에 직접 주입
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:dia:status:{dia_task_id}",
                result_key=f"task:dia:result:{dia_task_id}",
                task_id=dia_task_id,
                result_dict={
                    **MOCK_DIA_RESULT,
                    "task_id": dia_task_id,
                    "stt_task_id": stt_task_id,
                },
            )
        )

        # DIA 결과 조회
        response = e2e_client.get(f"/api/v1/diarizations/{dia_task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        # 세그먼트에 speaker_id 필드 존재 확인
        assert len(data["segments"]) > 0
        for segment in data["segments"]:
            assert "speaker_id" in segment
            assert segment["speaker_id"] is not None


# ---------------------------------------------------------------------------
# REQ-E2E-005: DIA → MIN 파이프라인 연결 검증
# ---------------------------------------------------------------------------


class TestDIAToMINPipeline:
    """DIA → MIN 파이프라인 단계 검증 (REQ-E2E-005)"""

    def test_min_request_with_dia_task_id(
        self,
        e2e_client: TestClient,
        e2e_redis: InMemoryRedis,
    ) -> None:
        """
        DIA 결과를 Redis에 주입한 후 MIN 요청 시 202 응답 검증
        diarization_task_id 연결로 파이프라인 체이닝 확인
        """
        import asyncio

        dia_task_id = "22222222-2222-2222-2222-222222222222"

        # DIA 결과 주입
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:dia:status:{dia_task_id}",
                result_key=f"task:dia:result:{dia_task_id}",
                task_id=dia_task_id,
                result_dict={**MOCK_DIA_RESULT, "task_id": dia_task_id},
            )
        )

        # MIN 요청 (diarization_task_id로 연결)
        response = e2e_client.post(
            "/api/v1/minutes",
            json={"diarization_task_id": dia_task_id},
        )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        # diarization_task_id가 응답에 포함되어야 함
        assert data["diarization_task_id"] == dia_task_id

    def test_min_result_has_speaker_stats(
        self,
        e2e_client: TestClient,
        e2e_redis: InMemoryRedis,
    ) -> None:
        """
        MIN 결과 조회 시 화자별 통계(speakers) 포함 검증
        """
        import asyncio

        min_task_id = "33333333-3333-3333-3333-333333333333"
        dia_task_id = "22222222-2222-2222-2222-222222222222"

        # MIN 결과를 Redis에 직접 주입
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:min:status:{min_task_id}",
                result_key=f"task:min:result:{min_task_id}",
                task_id=min_task_id,
                result_dict={
                    **MOCK_MIN_RESULT,
                    "task_id": min_task_id,
                    "diarization_task_id": dia_task_id,
                },
            )
        )

        # MIN 결과 조회
        response = e2e_client.get(f"/api/v1/minutes/{min_task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        # speakers 통계 존재 확인
        assert "speakers" in data
        assert len(data["speakers"]) > 0
        # 각 화자에 통계 필드 존재 확인
        for speaker in data["speakers"]:
            assert "speaker_id" in speaker
            assert "total_speaking_time" in speaker
            assert "segment_count" in speaker


# ---------------------------------------------------------------------------
# REQ-E2E-006: MIN → SUM 파이프라인 연결 검증
# ---------------------------------------------------------------------------


class TestMINToSUMPipeline:
    """MIN → SUM 파이프라인 단계 검증 (REQ-E2E-006)"""

    def test_sum_request_with_min_task_id(
        self,
        e2e_client: TestClient,
        e2e_redis: InMemoryRedis,
    ) -> None:
        """
        MIN 결과를 Redis에 주입한 후 SUM 요청 시 202 응답 검증
        minutes_task_id 연결로 파이프라인 체이닝 확인
        """
        import asyncio

        min_task_id = "33333333-3333-3333-3333-333333333333"

        # MIN 결과 주입
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:min:status:{min_task_id}",
                result_key=f"task:min:result:{min_task_id}",
                task_id=min_task_id,
                result_dict={**MOCK_MIN_RESULT, "task_id": min_task_id},
            )
        )

        # SUM 요청 (minutes_task_id로 연결)
        response = e2e_client.post(
            "/api/v1/summaries",
            json={"minutes_task_id": min_task_id},
        )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        # minutes_task_id가 응답에 포함되어야 함
        assert data["minutes_task_id"] == min_task_id

    def test_sum_result_has_summary(
        self,
        e2e_client: TestClient,
        e2e_redis: InMemoryRedis,
    ) -> None:
        """
        SUM 결과 조회 시 summary_text 포함 검증
        """
        import asyncio

        sum_task_id = "44444444-4444-4444-4444-444444444444"
        min_task_id = "33333333-3333-3333-3333-333333333333"

        # SUM 결과를 Redis에 직접 주입
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:sum:status:{sum_task_id}",
                result_key=f"task:sum:result:{sum_task_id}",
                task_id=sum_task_id,
                result_dict={
                    **MOCK_SUM_RESULT,
                    "task_id": sum_task_id,
                    "minutes_task_id": min_task_id,
                },
            )
        )

        # SUM 결과 조회
        response = e2e_client.get(f"/api/v1/summaries/{sum_task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        # summary_text 존재 및 비어있지 않음 확인
        assert "summary_text" in data
        assert len(data["summary_text"]) > 0


# ---------------------------------------------------------------------------
# REQ-E2E-007, REQ-E2E-009, REQ-E2E-010: 전체 파이프라인 검증
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """전체 STT → DIA → MIN → SUM 파이프라인 검증 (REQ-E2E-007, 009, 010)"""

    def test_full_pipeline_stt_to_sum(
        self,
        e2e_client: TestClient,
        e2e_redis: InMemoryRedis,
    ) -> None:
        """
        전체 4단계 파이프라인 순차 실행 및 task_id 체이닝 검증 (REQ-E2E-007)
        STT → DIA → MIN → SUM 순서로 각 단계 결과를 Redis에 주입하며 진행
        """
        import asyncio


        # 단계 1: STT 업로드
        wav_bytes = make_test_wav(duration_seconds=1)
        stt_response = e2e_client.post(
            "/api/v1/transcriptions",
            files={"file": ("test.wav", wav_bytes, "audio/wav")},
            data={"language": "ko"},
        )
        assert stt_response.status_code == 201
        stt_task_id = stt_response.json()["task_id"]

        # STT 결과 시뮬레이션 (Celery 워커가 완료한 것처럼)
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:status:{stt_task_id}",
                result_key=f"task:result:{stt_task_id}",
                task_id=stt_task_id,
                result_dict={**MOCK_STT_RESULT, "task_id": stt_task_id},
            )
        )

        # 단계 2: DIA 요청 (stt_task_id 체이닝)
        dia_response = e2e_client.post(
            "/api/v1/diarizations",
            json={"stt_task_id": stt_task_id},
        )
        assert dia_response.status_code == 202
        dia_task_id = dia_response.json()["task_id"]

        # DIA 결과 시뮬레이션
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:dia:status:{dia_task_id}",
                result_key=f"task:dia:result:{dia_task_id}",
                task_id=dia_task_id,
                result_dict={
                    **MOCK_DIA_RESULT,
                    "task_id": dia_task_id,
                    "stt_task_id": stt_task_id,
                },
            )
        )

        # 단계 3: MIN 요청 (dia_task_id 체이닝)
        min_response = e2e_client.post(
            "/api/v1/minutes",
            json={"diarization_task_id": dia_task_id},
        )
        assert min_response.status_code == 202
        min_task_id = min_response.json()["task_id"]

        # MIN 결과 시뮬레이션
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:min:status:{min_task_id}",
                result_key=f"task:min:result:{min_task_id}",
                task_id=min_task_id,
                result_dict={
                    **MOCK_MIN_RESULT,
                    "task_id": min_task_id,
                    "diarization_task_id": dia_task_id,
                },
            )
        )

        # 단계 4: SUM 요청 (min_task_id 체이닝)
        sum_response = e2e_client.post(
            "/api/v1/summaries",
            json={"minutes_task_id": min_task_id},
        )
        assert sum_response.status_code == 202
        sum_task_id = sum_response.json()["task_id"]

        # SUM 결과 시뮬레이션
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:sum:status:{sum_task_id}",
                result_key=f"task:sum:result:{sum_task_id}",
                task_id=sum_task_id,
                result_dict={
                    **MOCK_SUM_RESULT,
                    "task_id": sum_task_id,
                    "minutes_task_id": min_task_id,
                },
            )
        )

        # 최종 SUM 결과 검증
        final_response = e2e_client.get(f"/api/v1/summaries/{sum_task_id}")
        assert final_response.status_code == 200
        final_data = final_response.json()
        assert final_data["status"] == "completed"
        assert final_data["summary_text"] != ""

    def test_status_endpoints_return_valid_status(
        self,
        e2e_client: TestClient,
        e2e_redis: InMemoryRedis,
    ) -> None:
        """
        4개 파이프라인 단계의 상태 엔드포인트가 유효한 status 반환 검증 (REQ-E2E-009)
        """
        import asyncio


        stt_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        dia_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        min_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        sum_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"

        # 각 단계 상태를 Redis에 주입
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:status:{stt_id}",
                result_key=f"task:result:{stt_id}",
                task_id=stt_id,
                result_dict={**MOCK_STT_RESULT, "task_id": stt_id},
            )
        )
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:dia:status:{dia_id}",
                result_key=f"task:dia:result:{dia_id}",
                task_id=dia_id,
                result_dict={
                    **MOCK_DIA_RESULT,
                    "task_id": dia_id,
                    "stt_task_id": stt_id,
                },
            )
        )
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:min:status:{min_id}",
                result_key=f"task:min:result:{min_id}",
                task_id=min_id,
                result_dict={
                    **MOCK_MIN_RESULT,
                    "task_id": min_id,
                    "diarization_task_id": dia_id,
                },
            )
        )
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:sum:status:{sum_id}",
                result_key=f"task:sum:result:{sum_id}",
                task_id=sum_id,
                result_dict={
                    **MOCK_SUM_RESULT,
                    "task_id": sum_id,
                    "minutes_task_id": min_id,
                },
            )
        )

        # STT 상태 확인
        r = e2e_client.get(f"/api/v1/transcriptions/{stt_id}/status")
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

        # DIA 상태 확인
        r = e2e_client.get(f"/api/v1/diarizations/{dia_id}/status")
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

        # MIN 상태 확인
        r = e2e_client.get(f"/api/v1/minutes/{min_id}/status")
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

        # SUM 상태 확인
        r = e2e_client.get(f"/api/v1/summaries/{sum_id}/status")
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_delete_endpoints_return_204(
        self,
        e2e_client: TestClient,
        e2e_redis: InMemoryRedis,
    ) -> None:
        """
        4개 파이프라인 단계의 삭제 엔드포인트가 204 응답 반환 검증 (REQ-E2E-010)
        """
        import asyncio


        stt_id = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
        dia_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"
        min_id = "11112222-1111-2222-1111-111122221111"
        sum_id = "22223333-2222-3333-2222-222233332222"

        # 각 단계 데이터를 Redis에 주입
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:status:{stt_id}",
                result_key=f"task:result:{stt_id}",
                task_id=stt_id,
                result_dict={**MOCK_STT_RESULT, "task_id": stt_id},
            )
        )
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:dia:status:{dia_id}",
                result_key=f"task:dia:result:{dia_id}",
                task_id=dia_id,
                result_dict={**MOCK_DIA_RESULT, "task_id": dia_id, "stt_task_id": stt_id},
            )
        )
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:min:status:{min_id}",
                result_key=f"task:min:result:{min_id}",
                task_id=min_id,
                result_dict={
                    **MOCK_MIN_RESULT,
                    "task_id": min_id,
                    "diarization_task_id": dia_id,
                },
            )
        )
        asyncio.run(
            inject_result(
                e2e_redis,
                status_key=f"task:sum:status:{sum_id}",
                result_key=f"task:sum:result:{sum_id}",
                task_id=sum_id,
                result_dict={
                    **MOCK_SUM_RESULT,
                    "task_id": sum_id,
                    "minutes_task_id": min_id,
                },
            )
        )

        # STT 삭제
        r = e2e_client.delete(f"/api/v1/transcriptions/{stt_id}")
        assert r.status_code == 204

        # DIA 삭제
        r = e2e_client.delete(f"/api/v1/diarizations/{dia_id}")
        assert r.status_code == 204

        # MIN 삭제
        r = e2e_client.delete(f"/api/v1/minutes/{min_id}")
        assert r.status_code == 204

        # SUM 삭제
        r = e2e_client.delete(f"/api/v1/summaries/{sum_id}")
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# REQ-E2E-008, REQ-E2E-011, REQ-E2E-012: 에러 처리 검증
# ---------------------------------------------------------------------------


class TestPipelineErrors:
    """파이프라인 에러 처리 검증 (REQ-E2E-008, 011, 012)"""

    def test_dia_with_nonexistent_stt(
        self,
        e2e_client: TestClient,
    ) -> None:
        """
        존재하지 않는 stt_task_id로 DIA 요청 시 동작 확인 (REQ-E2E-008)
        DIA는 stt_task_id 유효성을 사전 검증하지 않고 202로 작업을 등록함
        실제 워커에서 결과 조회 시 404가 발생하는 구조
        """
        fake_stt_id = "99999999-9999-9999-9999-999999999999"

        # DIA 요청 자체는 202로 처리됨 (워커가 실제로 결과를 찾지 못하는 시점에 오류)
        response = e2e_client.post(
            "/api/v1/diarizations",
            json={"stt_task_id": fake_stt_id},
        )
        # API는 202 반환 (작업 등록 성공), 실제 실패는 워커 실행 시 발생
        assert response.status_code == 202

    def test_min_with_nonexistent_dia(
        self,
        e2e_client: TestClient,
    ) -> None:
        """
        존재하지 않는 diarization_task_id로 MIN 요청 시 동작 확인 (REQ-E2E-008)
        MIN API는 작업 등록만 처리하므로 202 반환
        """
        fake_dia_id = "99999999-9999-9999-9999-999999999998"

        response = e2e_client.post(
            "/api/v1/minutes",
            json={"diarization_task_id": fake_dia_id},
        )
        # API는 202 반환 (작업 등록 성공)
        assert response.status_code == 202

    def test_sum_with_nonexistent_min(
        self,
        e2e_client: TestClient,
    ) -> None:
        """
        존재하지 않는 minutes_task_id로 SUM 요청 시 동작 확인 (REQ-E2E-008)
        SUM API는 작업 등록만 처리하므로 202 반환
        """
        fake_min_id = "99999999-9999-9999-9999-999999999997"

        response = e2e_client.post(
            "/api/v1/summaries",
            json={"minutes_task_id": fake_min_id},
        )
        # API는 202 반환 (작업 등록 성공)
        assert response.status_code == 202

    def test_dia_concurrent_limit_429(
        self,
        e2e_client: TestClient,
        e2e_redis: InMemoryRedis,
    ) -> None:
        """
        DIA 동시 처리 한도(2개) 초과 시 429 응답 검증 (REQ-E2E-011)
        active_dia_jobs Set을 미리 채워 한도 초과 상황 시뮬레이션
        """
        import asyncio


        # active_dia_jobs에 2개 작업 등록 (한도=2이므로 이미 가득 찬 상태)
        asyncio.run(e2e_redis.sadd("active_dia_jobs", "job1", "job2"))

        stt_task_id = "55555555-5555-5555-5555-555555555555"

        # 3번째 DIA 요청 → 429 응답 기대
        response = e2e_client.post(
            "/api/v1/diarizations",
            json={"stt_task_id": stt_task_id},
        )

        assert response.status_code == 429

    def test_min_concurrent_limit_429(
        self,
        e2e_client: TestClient,
        e2e_redis: InMemoryRedis,
    ) -> None:
        """
        MIN 동시 처리 한도(3개) 초과 시 429 응답 검증 (REQ-E2E-012)
        active_min_jobs Set을 미리 채워 한도 초과 상황 시뮬레이션
        """
        import asyncio


        # active_min_jobs에 3개 작업 등록 (한도=3이므로 가득 찬 상태)
        asyncio.run(
            e2e_redis.sadd("active_min_jobs", "min_job1", "min_job2", "min_job3")
        )

        dia_task_id = "66666666-6666-6666-6666-666666666666"

        # 4번째 MIN 요청 → 429 응답 기대
        response = e2e_client.post(
            "/api/v1/minutes",
            json={"diarization_task_id": dia_task_id},
        )

        assert response.status_code == 429

    def test_sum_concurrent_limit_429(
        self,
        e2e_client: TestClient,
        e2e_redis: InMemoryRedis,
    ) -> None:
        """
        SUM 동시 처리 한도(2개) 초과 시 429 응답 검증 (REQ-E2E-012)
        active_sum_jobs Set을 미리 채워 한도 초과 상황 시뮬레이션
        """
        import asyncio


        # active_sum_jobs에 2개 작업 등록 (한도=2이므로 가득 찬 상태)
        asyncio.run(e2e_redis.sadd("active_sum_jobs", "sum_job1", "sum_job2"))

        min_task_id = "77777777-7777-7777-7777-777777777777"

        # 3번째 SUM 요청 → 429 응답 기대
        response = e2e_client.post(
            "/api/v1/summaries",
            json={"minutes_task_id": min_task_id},
        )

        assert response.status_code == 429
