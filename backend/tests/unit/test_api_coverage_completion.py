import io
import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect
from starlette.datastructures import UploadFile

from backend.app.exceptions import NotFoundError, ServiceUnavailableError


class _AsyncSessionContext:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _user(user_id: uuid.UUID | None = None):
    return SimpleNamespace(
        id=user_id or uuid.uuid4(),
        email="user@example.com",
        display_name="User",
        avatar_url=None,
        is_active=True,
    )


def _db_with_scalar(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    db = AsyncMock()
    db.execute.return_value = result
    return db


def _history_record(task_id: str = "task-1"):
    now = datetime.now(UTC)
    return SimpleNamespace(
        task_id=task_id,
        task_type="minutes",
        status="completed",
        created_at=now,
        completed_at=now,
        error_message=None,
        result_data={"text": "회의록"},
        input_metadata={"language": "ko"},
    )


def _bookmark(user_id: uuid.UUID | None = None):
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        task_id="task-1",
        segment_start=1.0,
        segment_end=2.0,
        text_snippet="중요",
        note="note",
        color="red",
        category="note",
        priority="medium",
        tags=["tag"],
        is_private=True,
        created_at=now,
        updated_at=now,
    )


def _speaker(user_id: uuid.UUID | None = None):
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        speaker_label="SPEAKER_00",
        display_name="Alice",
        role="PM",
        note="",
        task_id=None,
        created_at=now,
        updated_at=now,
    )


def _vocabulary():
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid.uuid4(), name="용어", words=["API"], created_at=now, updated_at=now
    )


@pytest.mark.asyncio
async def test_history_api_direct_success_and_not_found_paths():
    from backend.app.api.v1.admin.history import (
        delete_history,
        get_history,
        get_result_service,
        list_history,
    )

    assert get_result_service() is not None

    record = _history_record()
    svc = SimpleNamespace(
        count_results=AsyncMock(return_value=1),
        list_results=AsyncMock(return_value=[record]),
        get_result=AsyncMock(return_value=record),
        delete_result=AsyncMock(side_effect=[True, False]),
    )
    db = AsyncMock()
    shared_result = MagicMock()
    shared_result.all.return_value = []
    db.execute.return_value = shared_result
    request = SimpleNamespace(state=SimpleNamespace())

    listing = await list_history(
        request=request,
        task_type="minutes",
        status="completed",
        page=2,
        page_size=5,
        db=db,
        svc=svc,
    )
    assert listing.total == 1
    assert listing.page == 2
    svc.list_results.assert_awaited_with(
        session=db,
        task_type="minutes",
        status="completed",
        limit=5,
        offset=5,
        owner_id=None,
        guest_session_id=None,
    )

    detail = await get_history("task-1", request=request, db=db, svc=svc)
    assert detail.result_data == {"text": "회의록"}

    await delete_history("task-1", request=request, db=db, svc=svc)
    with pytest.raises(NotFoundError):
        await delete_history("missing", request=request, db=db, svc=svc)

    svc.get_result.return_value = None
    with pytest.raises(NotFoundError):
        await get_history("missing", request=request, db=db, svc=svc)


def test_template_validate_file_rejects_signature_mismatch():
    from backend.app.api.v1.admin.templates import _validate_file

    ok, message = _validate_file("template.pdf", 10, b"not-a-pdf")
    assert ok is False
    assert "시그니처" in message


@pytest.mark.asyncio
async def test_tone_api_missing_and_processing_paths():
    from backend.app.api.v1.analytics import tone

    redis = AsyncMock()
    with patch.object(tone.settings, "tone_model", "enabled"):
        redis.get.return_value = None
        with pytest.raises(NotFoundError):
            await tone.get_tone_by_meeting("meeting-1", redis_client=redis)
        with pytest.raises(NotFoundError):
            await tone.get_tone_status("missing", redis_client=redis)

        redis.get.return_value = json.dumps({"status": "processing", "progress": 0.2})
        status = await tone.get_tone_status("task-1", redis_client=redis)
        assert status.status == "processing"

        redis.get.side_effect = [None, json.dumps({"status": "processing"})]
        result = await tone.get_tone_result("task-1", redis_client=redis)
        assert result.status == "processing"

    with patch.object(tone.settings, "tone_model", ""):
        with pytest.raises(ServiceUnavailableError):
            tone._check_tone_enabled()


@pytest.mark.asyncio
async def test_vocabulary_api_direct_crud_paths():
    from backend.app.api.v1.analytics.vocabulary import (
        create_vocabulary,
        delete_vocabulary,
        get_vocabulary,
        list_vocabularies,
        update_vocabulary,
    )
    from backend.schemas.vocabulary import VocabularyCreate, VocabularyUpdate

    vocab = _vocabulary()
    svc = SimpleNamespace(
        create=AsyncMock(return_value=vocab),
        list_all=AsyncMock(return_value=([vocab], 1)),
        get_by_id=AsyncMock(return_value=vocab),
        update=AsyncMock(return_value=vocab),
        delete=AsyncMock(),
    )
    db = AsyncMock()

    created = await create_vocabulary(VocabularyCreate(name="용어", words=["API"]), db=db, svc=svc)
    assert created.name == "용어"
    listed = await list_vocabularies(page=2, page_size=10, db=db, svc=svc)
    assert listed.total == 1
    svc.list_all.assert_awaited_with(db, limit=10, offset=10)
    assert (await get_vocabulary(vocab.id, db=db, svc=svc)).id == vocab.id
    assert (
        await update_vocabulary(vocab.id, VocabularyUpdate(name="새 용어"), db=db, svc=svc)
    ).id == vocab.id
    await delete_vocabulary(vocab.id, db=db, svc=svc)
    svc.delete.assert_awaited_once_with(db, vocab.id)


@pytest.mark.asyncio
async def test_quality_assessment_success_and_monitoring_paths():
    from backend.app.api.v1.audio.quality_assessment import (
        get_improvement_suggestions,
        get_live_quality_score,
        get_quality_assessment,
        list_quality_feedback,
        request_quality_assessment,
        submit_quality_feedback,
    )
    from backend.schemas.quality import (
        AssessmentSummary,
        FeedbackCategory,
        LiveQualityScoreResponse,
        QualityAssessmentRequest,
        QualityAssessmentResponse,
        QualityFeedbackCreate,
        QualityFeedbackResponse,
        QualityFeedbackSummary,
        QualityTrendsResponse,
    )

    now = datetime.now(UTC)
    task = SimpleNamespace(result_data={"title": "회의", "segments": [{"text": "결정 사항"}]})
    db = _db_with_scalar(task)
    assessment = QualityAssessmentResponse(
        task_id="task-1",
        assessment_summary=AssessmentSummary(
            overall_score=90, grade="A", total_issues=0, critical_issues=0
        ),
    )
    feedback = QualityFeedbackResponse(
        id="fb-1", task_id="task-1", rating=5, category=FeedbackCategory.OTHER, created_at=now
    )
    svc = SimpleNamespace(
        assess_minutes=AsyncMock(return_value=assessment),
        get_improvement_suggestions=AsyncMock(return_value=[]),
        generate_action_plan=AsyncMock(return_value=[]),
        compute_live_score=AsyncMock(
            return_value=LiveQualityScoreResponse(
                task_id="task-1",
                overall_score=90,
                grade="A",
                completeness_score=90,
                clarity_score=90,
                structure_score=90,
                word_count=10,
                computed_at=now,
            )
        ),
        submit_feedback=AsyncMock(return_value=feedback),
        get_feedback_summary=AsyncMock(
            return_value=QualityFeedbackSummary(task_id="task-1", total_feedbacks=1, avg_rating=5)
        ),
        get_quality_trends=AsyncMock(
            return_value=QualityTrendsResponse(task_id="task-1", points_count=0)
        ),
    )

    assert (await get_quality_assessment("task-1", db=db, svc=svc)).task_id == "task-1"
    assert (
        await request_quality_assessment(
            "task-1", QualityAssessmentRequest(criteria={"x": 1}), db=db, svc=svc
        )
    ).task_id == "task-1"
    improvements = await get_improvement_suggestions("task-1", db=db, svc=svc)
    assert improvements.total_improvements == 0
    assert (await get_live_quality_score("task-1", persist=False, db=db, svc=svc)).grade == "A"
    assert (
        await submit_quality_feedback(
            "task-1",
            QualityFeedbackCreate(rating=5, category=FeedbackCategory.OTHER),
            db=db,
            svc=svc,
        )
    ).id == "fb-1"
    assert (await list_quality_feedback("task-1", db=db, svc=svc)).total_feedbacks == 1


@pytest.mark.asyncio
async def test_quality_assessment_not_found_and_error_paths():
    from backend.app.api.v1.audio.quality_assessment import (
        _load_minutes_text_or_404,
        get_improvement_suggestions,
        get_live_quality_score,
        get_quality_assessment,
        request_quality_assessment,
        submit_quality_feedback,
    )
    from backend.app.exceptions import InternalServerError
    from backend.schemas.quality import (
        FeedbackCategory,
        QualityAssessmentRequest,
        QualityFeedbackCreate,
    )

    svc = SimpleNamespace(
        assess_minutes=AsyncMock(side_effect=RuntimeError("assess failed")),
        get_improvement_suggestions=AsyncMock(side_effect=RuntimeError("improve failed")),
        compute_live_score=AsyncMock(side_effect=RuntimeError("score failed")),
        submit_feedback=AsyncMock(side_effect=RuntimeError("feedback failed")),
    )

    with pytest.raises(NotFoundError):
        await get_quality_assessment("missing", db=_db_with_scalar(None), svc=svc)
    with pytest.raises(NotFoundError):
        await get_quality_assessment(
            "empty", db=_db_with_scalar(SimpleNamespace(result_data={})), svc=svc
        )
    with pytest.raises(InternalServerError):
        await get_quality_assessment(
            "task-1",
            db=_db_with_scalar(SimpleNamespace(result_data={"text": "회의록"})),
            svc=svc,
        )

    with pytest.raises(NotFoundError):
        await request_quality_assessment(
            "missing", QualityAssessmentRequest(), db=_db_with_scalar(None), svc=svc
        )
    with pytest.raises(InternalServerError):
        await request_quality_assessment(
            "task-1",
            QualityAssessmentRequest(),
            db=_db_with_scalar(SimpleNamespace(result_data={"text": "회의록"})),
            svc=svc,
        )

    with pytest.raises(NotFoundError):
        await get_improvement_suggestions("missing", db=_db_with_scalar(None), svc=svc)
    with pytest.raises(InternalServerError):
        await get_improvement_suggestions(
            "task-1", db=_db_with_scalar(SimpleNamespace(result_data={"text": "회의록"})), svc=svc
        )

    with pytest.raises(NotFoundError):
        await _load_minutes_text_or_404(_db_with_scalar(None), "missing")
    with pytest.raises(NotFoundError):
        await _load_minutes_text_or_404(_db_with_scalar(SimpleNamespace(result_data={})), "empty")
    with pytest.raises(InternalServerError):
        await get_live_quality_score(
            "task-1", db=_db_with_scalar(SimpleNamespace(result_data={"text": "회의록"})), svc=svc
        )

    with pytest.raises(NotFoundError):
        await submit_quality_feedback(
            "missing",
            QualityFeedbackCreate(rating=1, category=FeedbackCategory.OTHER),
            db=_db_with_scalar(None),
            svc=svc,
        )
    with pytest.raises(InternalServerError):
        await submit_quality_feedback(
            "task-1",
            QualityFeedbackCreate(rating=1, category=FeedbackCategory.OTHER),
            db=_db_with_scalar(SimpleNamespace(result_data={"text": "회의록"})),
            svc=svc,
        )


@pytest.mark.asyncio
async def test_bookmark_api_direct_crud_and_search_paths():
    from backend.app.api.v1.collaboration.bookmarks import (
        create_bookmark,
        delete_bookmark,
        get_bookmark,
        list_bookmarks,
        search_bookmarks,
        update_bookmark,
    )
    from backend.schemas.bookmark import BookmarkCreate, BookmarkSearchResponse, BookmarkUpdate

    user = _user()
    bookmark = _bookmark(user.id)
    svc = SimpleNamespace(
        create=AsyncMock(return_value=bookmark),
        list_for_user=AsyncMock(return_value=([bookmark], 1)),
        get_by_id=AsyncMock(return_value=bookmark),
        update=AsyncMock(return_value=bookmark),
        delete=AsyncMock(),
        search_bookmarks=AsyncMock(
            return_value=BookmarkSearchResponse(
                items=[],
                total=0,
                page=1,
                page_size=10,
                total_pages=0,
            )
        ),
    )
    db = AsyncMock()

    created = await create_bookmark(
        BookmarkCreate(task_id="task-1", segment_start=1, segment_end=2),
        db=db,
        user=user,
        svc=svc,
    )
    assert created.user_id == user.id
    listed = await list_bookmarks(task_id="task-1", page=2, page_size=10, db=db, user=user, svc=svc)
    assert listed.total == 1
    assert (await get_bookmark(bookmark.id, db=db, user=user, svc=svc)).id == bookmark.id
    assert (
        await update_bookmark(bookmark.id, BookmarkUpdate(note="n"), db=db, user=user, svc=svc)
    ).id == bookmark.id
    await delete_bookmark(bookmark.id, db=db, user=user, svc=svc)
    search = await search_bookmarks(
        query="q",
        category="note",
        priority="medium",
        tags=" a, b ,,",
        task_id=None,
        has_tags=None,
        date_from="2026-01-01T00:00:00Z",
        date_to="2026-01-02T00:00:00Z",
        page=1,
        page_size=10,
        sort_by="created_at",
        sort_order="desc",
        db=db,
        user=user,
        svc=svc,
    )
    assert search.total == 0


@pytest.mark.asyncio
async def test_speaker_api_direct_crud_and_voice_paths():
    from backend.app.api.v1.collaboration.speakers import (
        analyze_speaker_sample,
        create_or_update_voice_profile,
        create_speaker,
        delete_speaker,
        get_speaker,
        get_voice_characteristics,
        list_speakers,
        update_speaker,
    )
    from backend.schemas.speaker import (
        SpeakerProfileCreate,
        SpeakerProfileUpdate,
        VoiceCharacteristics,
        VoiceProfileCreateRequest,
        VoiceSampleAnalysis,
    )

    user = _user()
    speaker = _speaker(user.id)
    now = datetime.now(UTC)
    characteristics = VoiceCharacteristics(
        speaker_profile_id=speaker.id,
        sample_count=1,
        total_duration_seconds=1.0,
        created_at=now,
        updated_at=now,
    )
    sample = VoiceSampleAnalysis(duration_seconds=1.0)
    svc = SimpleNamespace(
        create=AsyncMock(return_value=speaker),
        list_for_user=AsyncMock(return_value=([speaker], 1)),
        get_by_id=AsyncMock(return_value=speaker),
        update=AsyncMock(return_value=speaker),
        delete=AsyncMock(),
    )
    voice_svc = SimpleNamespace(
        analyze_upload=AsyncMock(return_value=(sample, characteristics)),
        create_or_replace_from_samples=AsyncMock(return_value=characteristics),
        get_characteristics=AsyncMock(return_value=characteristics),
        to_characteristics_response=MagicMock(return_value=characteristics),
    )
    db = AsyncMock()

    assert (
        await create_speaker(
            SpeakerProfileCreate(speaker_label="SPEAKER_00", display_name="Alice"),
            db=db,
            user=user,
            svc=svc,
        )
    ).id == speaker.id
    assert (await list_speakers(page=2, page_size=10, db=db, user=user, svc=svc)).total == 1
    assert (await get_speaker(speaker.id, db=db, user=user, svc=svc)).id == speaker.id
    assert (
        await update_speaker(
            speaker.id, SpeakerProfileUpdate(display_name="A"), db=db, user=user, svc=svc
        )
    ).id == speaker.id
    await delete_speaker(speaker.id, db=db, user=user, svc=svc)
    upload = UploadFile(file=io.BytesIO(b"wav"), filename="sample.wav")
    analyzed = await analyze_speaker_sample(
        speaker.id, upload, db=db, user=user, svc=svc, voice_svc=voice_svc
    )
    assert analyzed.speaker_profile_id == speaker.id
    assert (
        await create_or_update_voice_profile(
            speaker.id,
            VoiceProfileCreateRequest(samples=[]),
            db=db,
            user=user,
            svc=svc,
            voice_svc=voice_svc,
        )
    ).speaker_profile_id == speaker.id
    assert (
        await get_voice_characteristics(speaker.id, db=db, user=user, svc=svc, voice_svc=voice_svc)
    ).speaker_profile_id == speaker.id


@pytest.mark.asyncio
async def test_batch_upload_marks_magic_byte_mismatch_failed():
    from backend.app.api.v1.transcription.batch import upload_batch_transcription

    upload = SimpleNamespace(
        filename="bad.wav",
        content_type="audio/wav",
        read=AsyncMock(return_value=b"bad"),
    )
    redis = AsyncMock()

    with (
        patch(
            "backend.app.api.v1.transcription.batch.validate_audio_format",
            side_effect=[(True, ""), (False, "bad signature")],
        ),
        patch(
            "backend.app.api.v1.transcription.batch.validate_file_size",
            return_value=(True, ""),
        ),
    ):
        response = await upload_batch_transcription(files=[upload], redis_client=redis)

    assert response.accepted == 0
    assert response.items[0].error == "bad signature"


@pytest.mark.asyncio
async def test_collab_connection_manager_and_auth_paths():
    from backend.app.api.v1.collaboration import collab

    assert collab.get_collab_service() is not None

    manager = collab.ConnectionManager()
    ws = SimpleNamespace(accept=AsyncMock(), send_text=AsyncMock())
    await manager.connect("task", "u1", ws)
    assert manager.get_room("task") == {"u1": ws}
    await manager.send_to_user("task", "u1", {"ok": True})
    ws.send_text.assert_awaited()
    manager.disconnect("task", "u1")
    assert manager.get_room("task") == {}

    bad_ws = SimpleNamespace(send_text=AsyncMock(side_effect=RuntimeError("closed")))
    good_ws = SimpleNamespace(send_text=AsyncMock())
    manager.rooms = {"task": {"bad": bad_ws, "skip": good_ws}}
    await manager.broadcast("task", {"msg": 1}, exclude_user_id="skip")
    assert "bad" not in manager.get_room("task")
    assert "skip" in manager.get_room("task")

    assert await collab.authenticate_ws_token(None, AsyncMock()) is None
    with patch("backend.app.api.v1.collaboration.collab.AuthService") as auth_cls:
        auth_cls.return_value.decode_access_token.side_effect = ValueError("bad")
        assert await collab.authenticate_ws_token("token", AsyncMock()) is None
        auth_cls.return_value.decode_access_token.side_effect = None
        auth_cls.return_value.decode_access_token.return_value = {}
        assert await collab.authenticate_ws_token("token", AsyncMock()) is None
        auth_cls.return_value.decode_access_token.return_value = {"sub": "not-a-uuid"}
        assert await collab.authenticate_ws_token("token", AsyncMock()) is None
        inactive = _user()
        inactive.is_active = False
        db = _db_with_scalar(inactive)
        auth_cls.return_value.decode_access_token.return_value = {"sub": str(inactive.id)}
        assert await collab.authenticate_ws_token("token", db) is None
        active = _user()
        db = _db_with_scalar(active)
        auth_cls.return_value.decode_access_token.return_value = {"sub": str(active.id)}
        assert await collab.authenticate_ws_token("token", db) is active


@pytest.mark.asyncio
async def test_collab_ws_message_loop_and_handlers():
    from backend.app.api.v1.collaboration import collab

    user = _user()
    db = AsyncMock()
    redis = AsyncMock()
    svc = SimpleNamespace(
        _ensure_task_exists=AsyncMock(return_value=True),
        add_presence=AsyncMock(return_value=(True, [{"user_id": str(user.id)}])),
        init_document_from_db=AsyncMock(return_value={"title": "old"}),
        get_document=AsyncMock(return_value=({"title": "old"}, {"title": datetime.now(UTC)})),
        apply_edit=AsyncMock(return_value=(True, datetime.now(UTC))),
        update_active_field=AsyncMock(),
        remove_presence=AsyncMock(return_value=[]),
        flush_to_db=AsyncMock(),
    )
    ws = SimpleNamespace(
        query_params={"token": "token"},
        accept=AsyncMock(),
        close=AsyncMock(),
        send_text=AsyncMock(),
        receive_text=AsyncMock(
            side_effect=[
                "{bad-json",
                json.dumps({"type": "unknown"}),
                json.dumps(
                    {
                        "type": "edit",
                        "payload": {
                            "field": "title",
                            "value": "new",
                            "client_timestamp": datetime.now(UTC).isoformat(),
                        },
                    }
                ),
                json.dumps({"type": "cursor", "payload": {"field": "title"}}),
                WebSocketDisconnect(),
            ]
        ),
    )
    collab.manager.rooms.clear()

    with (
        patch("backend.app.dependencies._session_factory", return_value=_AsyncSessionContext(db)),
        patch(
            "backend.app.api.v1.collaboration.collab.authenticate_ws_token",
            AsyncMock(return_value=user),
        ),
        patch("backend.app.api.v1.collaboration.collab.get_collab_service", return_value=svc),
        patch("backend.app.api.v1.collaboration.collab.get_redis_client", return_value=redis),
    ):
        await collab.collab_ws(ws, "task-1")

    ws.accept.assert_awaited_once()
    svc.apply_edit.assert_awaited()
    svc.update_active_field.assert_awaited_once()
    svc.flush_to_db.assert_awaited_once()


@pytest.mark.asyncio
async def test_collab_ws_close_paths_and_handler_edge_cases():
    from backend.app.api.v1.collaboration import collab

    user = _user()
    db = AsyncMock()
    redis = AsyncMock()
    ws = SimpleNamespace(query_params={"token": "token"}, close=AsyncMock())

    with (
        patch("backend.app.dependencies._session_factory", return_value=_AsyncSessionContext(db)),
        patch(
            "backend.app.api.v1.collaboration.collab.authenticate_ws_token",
            AsyncMock(return_value=None),
        ),
    ):
        await collab.collab_ws(ws, "task-1")
    ws.close.assert_awaited()

    svc = SimpleNamespace(_ensure_task_exists=AsyncMock(return_value=False))
    ws.close.reset_mock()
    with (
        patch("backend.app.dependencies._session_factory", return_value=_AsyncSessionContext(db)),
        patch(
            "backend.app.api.v1.collaboration.collab.authenticate_ws_token",
            AsyncMock(return_value=user),
        ),
        patch("backend.app.api.v1.collaboration.collab.get_collab_service", return_value=svc),
    ):
        await collab.collab_ws(ws, "task-1")
    ws.close.assert_awaited()

    svc = SimpleNamespace(
        _ensure_task_exists=AsyncMock(return_value=True),
        add_presence=AsyncMock(return_value=(False, [])),
    )
    ws.close.reset_mock()
    with (
        patch("backend.app.dependencies._session_factory", return_value=_AsyncSessionContext(db)),
        patch(
            "backend.app.api.v1.collaboration.collab.authenticate_ws_token",
            AsyncMock(return_value=user),
        ),
        patch("backend.app.api.v1.collaboration.collab.get_collab_service", return_value=svc),
        patch("backend.app.api.v1.collaboration.collab.get_redis_client", return_value=redis),
    ):
        await collab.collab_ws(ws, "task-1")
    ws.close.assert_awaited()

    fake_manager = SimpleNamespace(
        send_to_user=AsyncMock(), broadcast=AsyncMock(), disconnect=MagicMock()
    )
    svc = SimpleNamespace(
        apply_edit=AsyncMock(return_value=(False, datetime.now(UTC))),
        update_active_field=AsyncMock(),
        remove_presence=AsyncMock(return_value=[{"user_id": "other"}]),
    )
    with (
        patch("backend.app.api.v1.collaboration.collab.manager", fake_manager),
        patch("backend.app.api.v1.collaboration.collab.get_collab_service", return_value=svc),
        patch("backend.app.api.v1.collaboration.collab.get_redis_client", return_value=redis),
    ):
        await collab._handle_edit("task", "u1", user, {})
        await collab._handle_edit("task", "u1", user, {"field": "title", "client_timestamp": "bad"})
        await collab._handle_edit(
            "task",
            "u1",
            user,
            {"field": "title", "value": "new", "client_timestamp": datetime.now(UTC).isoformat()},
        )
        await collab._handle_cursor("task", "u1", {})
        await collab._handle_disconnect("task", "u1", user)

    assert fake_manager.send_to_user.await_count >= 3
    fake_manager.broadcast.assert_awaited()


@pytest.mark.asyncio
async def test_collab_ws_logs_unexpected_receive_error():
    from backend.app.api.v1.collaboration import collab

    user = _user()
    db = AsyncMock()
    redis = AsyncMock()
    svc = SimpleNamespace(
        _ensure_task_exists=AsyncMock(return_value=True),
        add_presence=AsyncMock(return_value=(True, [])),
        init_document_from_db=AsyncMock(return_value={}),
        get_document=AsyncMock(return_value=({}, {})),
        remove_presence=AsyncMock(return_value=[{"user_id": "other"}]),
    )
    ws = SimpleNamespace(
        query_params={"token": "token"},
        accept=AsyncMock(),
        close=AsyncMock(),
        send_text=AsyncMock(),
        receive_text=AsyncMock(side_effect=RuntimeError("receive failed")),
    )
    collab.manager.rooms.clear()

    with (
        patch("backend.app.dependencies._session_factory", return_value=_AsyncSessionContext(db)),
        patch(
            "backend.app.api.v1.collaboration.collab.authenticate_ws_token",
            AsyncMock(return_value=user),
        ),
        patch("backend.app.api.v1.collaboration.collab.get_collab_service", return_value=svc),
        patch("backend.app.api.v1.collaboration.collab.get_redis_client", return_value=redis),
    ):
        await collab.collab_ws(ws, "task-1")

    ws.accept.assert_awaited_once()
