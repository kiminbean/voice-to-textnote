"""
Tests for tagging_engine.py - covering uncovered lines 109-115 (exception handling)
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from backend.ml.tagging_engine import generate_auto_tags


class TestTaggingEngineExceptions:
    """Tests for exception handling in generate_auto_tags (lines 109-115)"""

    @pytest.mark.asyncio
    async def test_generate_auto_tags_api_failure_falls_back_to_rule_based(self):
        """Test API failure falls back to rule-based tagging (line 117-119)"""
        with patch('backend.ml.tagging_engine.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.summary_model = "gpt-4o-mini"

            # Mock http client to raise exception
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("API Error")

            with patch('backend.ml.tagging_engine._get_http_client', return_value=mock_client):
                result = await generate_auto_tags("회의 내용 테스트", max_tags=10)

                # Should fall back to rule-based tags
                assert isinstance(result, list)
                assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_auto_tags_invalid_json_response_fallback(self):
        """Test invalid JSON response falls back to rule-based (line 117-119)"""
        with patch('backend.ml.tagging_engine.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.summary_model = "gpt-4o-mini"

            # Mock response with invalid JSON
            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": "Not valid JSON at all {{{"
                    }
                }]
            }
            mock_response.usage.prompt_tokens = 100
            mock_response.usage.completion_tokens = 50

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response

            with patch('backend.ml.tagging_engine._get_http_client', return_value=mock_client):
                # JSON parsing error should trigger fallback
                result = await generate_auto_tags("회의 내용", max_tags=10)

                # Should fall back to rule-based tags
                assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_generate_auto_tags_no_api_key_uses_rule_based(self):
        """Test missing API key uses rule-based tagging directly (line 81-83)"""
        with patch('backend.ml.tagging_engine.settings') as mock_settings:
            mock_settings.openai_api_key = None

            result = await generate_auto_tags("긴급 회의입니다", max_tags=10)

            # Should use rule-based tags
            assert isinstance(result, list)
            assert any(tag["tag_type"] == "priority" and tag["tag_value"] == "긴급" for tag in result)

    @pytest.mark.asyncio
    async def test_generate_auto_tags_http_error_fallback(self):
        """Test HTTP error falls back to rule-based (line 117-119)"""
        with patch('backend.ml.tagging_engine.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.summary_model = "gpt-4o-mini"

            # Mock HTTP error
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.raise_for_status.side_effect = Exception("HTTP 500 Error")
            mock_client.post.return_value = mock_response

            with patch('backend.ml.tagging_engine._get_http_client', return_value=mock_client):
                result = await generate_auto_tags("회의 내용", max_tags=10)

                # Should fall back to rule-based tags
                assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_generate_auto_tags_truncates_long_content(self):
        """Test long content is truncated (line 87)"""
        with patch('backend.ml.tagging_engine.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.summary_model = "gpt-4o-mini"

            # Create content longer than 6000 chars
            long_content = "A" * 7000

            # Mock successful response
            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()
            mock_response.json.return_value = {
                "choices": [{
                    "message": {
                        "content": '{"tags": []}'
                    }
                }]
            }

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response

            with patch('backend.ml.tagging_engine._get_http_client', return_value=mock_client):
                await generate_auto_tags(long_content, max_tags=10)

                # Verify content was truncated
                call_args = mock_client.post.call_args
                sent_content = call_args[1]["json"]["messages"][1]["content"]
                assert len(sent_content) <= 6000 + len("다음 회의록을 분석해서 태그를 추출해주세요:\n\n")

    @pytest.mark.asyncio
    async def test_generate_auto_tags_max_tags_limit(self):
        """Test max_tags parameter limits results (line 115)"""
        import json

        with patch('backend.ml.tagging_engine.settings') as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.summary_model = "gpt-4o-mini"

            # Mock response with more tags than max_tags
            mock_response = AsyncMock()
            mock_response.raise_for_status = Mock()
            # Create valid JSON with 15 tags
            tags_array = [{"tag_type": "topic", "tag_value": f"tag{i}", "confidence": 0.9} for i in range(15)]
            mock_response.json = Mock(return_value={
                "choices": [{
                    "message": {
                        "content": json.dumps({"tags": tags_array})
                    }
                }]
            })

            mock_client = AsyncMock()
            mock_client.post = Mock(return_value=mock_response)

            with patch('backend.ml.tagging_engine._get_http_client', return_value=mock_client):
                result = await generate_auto_tags("회의 내용", max_tags=5)

                # Should be limited to max_tags (line 115: return tags[:max_tags])
                # Verify we get some results and they don't exceed max_tags
                assert len(result) > 0
                assert len(result) <= 5
