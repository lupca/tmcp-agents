import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from brand_identity_service import brand_identity_event_generator, _parse_json_response


# --- Unit tests for _parse_json_response ---

class TestParseJsonResponse:
    def test_parse_clean_json(self):
        raw = '{"brandName": "Test", "slogan": "Hello"}'
        result = _parse_json_response(raw)
        assert result["brandName"] == "Test"
        assert result["slogan"] == "Hello"

    def test_parse_json_with_whitespace(self):
        raw = '  \n  {"brandName": "Test"}  \n  '
        result = _parse_json_response(raw)
        assert result["brandName"] == "Test"

    def test_parse_json_in_code_fence(self):
        raw = 'Here is the result:\n```json\n{"brandName": "Test"}\n```\n'
        result = _parse_json_response(raw)
        assert result["brandName"] == "Test"

    def test_parse_json_with_surrounding_text(self):
        raw = 'Based on my analysis:\n{"brandName": "Test", "slogan": "Go"}\nThat is my result.'
        result = _parse_json_response(raw)
        assert result["brandName"] == "Test"

    def test_parse_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Could not parse JSON"):
            _parse_json_response("This is not JSON at all")

    def test_parse_full_brand_identity(self):
        raw = json.dumps({
            "brandName": "Aurora",
            "slogan": "Light the way",
            "missionStatement": "We illuminate possibilities.",
            "keywords": ["innovation", "light", "clarity", "growth", "trust"],
            "colorPalette": ["#6c5ce7", "#00cec9", "#fd79a8", "#ffeaa7", "#2d3436"],
        })
        result = _parse_json_response(raw)
        assert result["brandName"] == "Aurora"
        assert len(result["keywords"]) == 5
        assert len(result["colorPalette"]) == 5


# --- SSE event generator tests ---

def _collect_events(raw_events):
    """Parse SSE event strings into dicts."""
    events = []
    for e in raw_events:
        if e.startswith("data: "):
            events.append(json.loads(e[6:].strip()))
    return events


class TestBrandIdentityEventGenerator:
    @pytest.mark.asyncio
    async def test_successful_generation(self):
        """Full happy path: MCP fetch -> LLM stream -> JSON parse -> done."""
        brand_json = json.dumps({
            "brandName": "TestBrand",
            "slogan": "Test Slogan",
            "missionStatement": "We test things.",
            "keywords": ["test", "quality"],
            "colorPalette": ["#000000", "#ffffff"],
        })

        # Mock MCP tool call
        mock_mcp_result = MagicMock()
        mock_mcp_result.content = [MagicMock(text='{"title": "My Worksheet", "content": "Business description here"}')]

        # Mock LLM streaming
        mock_chunk = MagicMock()
        mock_chunk.content = brand_json

        async def mock_astream(*args, **kwargs):
            yield mock_chunk

        mock_llm = MagicMock()
        mock_llm.astream = mock_astream

        with patch("brand_identity_service.execute_mcp_tool", new_callable=AsyncMock, return_value=mock_mcp_result), \
             patch("brand_identity_service.get_ollama_llm", return_value=mock_llm):

            events = []
            async for event in brand_identity_event_generator("ws123", "English"):
                events.append(event)

            parsed = _collect_events(events)

            # Should have: status(fetching_worksheet), status(analyzing), chunk, done
            types = [e["type"] for e in parsed]
            assert "status" in types
            assert "chunk" in types
            assert "done" in types

            # done event should have brandIdentity
            done_event = next(e for e in parsed if e["type"] == "done")
            assert done_event["brandIdentity"]["brandName"] == "TestBrand"

    @pytest.mark.asyncio
    async def test_mcp_failure_emits_error(self):
        """When MCP tool call fails, should emit an error event."""
        with patch("brand_identity_service.execute_mcp_tool", new_callable=AsyncMock, side_effect=Exception("MCP connection refused")):

            events = []
            async for event in brand_identity_event_generator("bad_id", "English"):
                events.append(event)

            parsed = _collect_events(events)
            error_events = [e for e in parsed if e["type"] == "error"]
            assert len(error_events) >= 1
            assert "Failed to fetch worksheet" in error_events[0]["error"]

    @pytest.mark.asyncio
    async def test_invalid_llm_json_emits_error(self):
        """When LLM returns non-JSON, should emit an error event."""
        mock_mcp_result = MagicMock()
        mock_mcp_result.content = [MagicMock(text='{"title": "WS", "content": "data"}')]

        mock_chunk = MagicMock()
        mock_chunk.content = "I cannot generate JSON right now, sorry!"

        async def mock_astream(*args, **kwargs):
            yield mock_chunk

        mock_llm = MagicMock()
        mock_llm.astream = mock_astream

        with patch("brand_identity_service.execute_mcp_tool", new_callable=AsyncMock, return_value=mock_mcp_result), \
             patch("brand_identity_service.get_ollama_llm", return_value=mock_llm):

            events = []
            async for event in brand_identity_event_generator("ws123", "English"):
                events.append(event)

            parsed = _collect_events(events)
            error_events = [e for e in parsed if e["type"] == "error"]
            assert len(error_events) >= 1
            assert "invalid response format" in error_events[0]["error"]
