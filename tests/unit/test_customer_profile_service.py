import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from customer_profile_service import customer_profile_event_generator


def _collect_events(raw_events):
    """Parse SSE event strings into dicts."""
    events = []
    for e in raw_events:
        if e.startswith("data: "):
            events.append(json.loads(e[6:].strip()))
    return events


MOCK_BRAND = {
    "brandName": "Aurora",
    "slogan": "Light the way",
    "missionStatement": "We illuminate possibilities.",
    "keywords": ["innovation", "light", "clarity"],
    "worksheetId": "ws_abc123",
    "colorPalette": ["#6c5ce7", "#00cec9"],
}

MOCK_WORKSHEET = {
    "title": "Business Worksheet",
    "content": "A tech startup focused on AI education for professionals.",
}

MOCK_PROFILE = {
    "personaName": "Tech-Savvy Tina",
    "summary": "Tina is a 32-year-old product manager who wants to upskill in AI.",
    "demographics": {
        "age": "28-35",
        "gender": "Female",
        "location": "Ho Chi Minh City",
        "occupation": "Product Manager",
        "income": "$40,000-60,000",
    },
    "psychographics": {
        "values": "Learning, Innovation, Career Growth",
        "interests": "AI, Technology, Online Courses",
        "personality": "Curious, Ambitious, Analytical",
    },
    "goalsAndMotivations": {
        "primaryGoal": "Master AI fundamentals",
        "secondaryGoal": "Lead AI-powered product development",
        "motivation": "Stay competitive in the job market",
    },
    "painPointsAndChallenges": {
        "primaryPain": "Lack of structured AI learning resources",
        "challenges": "Balancing work and learning",
        "frustrations": "Overwhelming amount of scattered information",
    },
}


class TestCustomerProfileEventGenerator:
    @pytest.mark.asyncio
    async def test_successful_generation(self):
        """Full happy path: fetch brand -> fetch worksheet -> LLM stream -> done."""
        mock_brand_result = MagicMock()
        mock_brand_result.content = [MagicMock(text=json.dumps(MOCK_BRAND))]

        mock_ws_result = MagicMock()
        mock_ws_result.content = [MagicMock(text=json.dumps(MOCK_WORKSHEET))]

        async def mock_execute_mcp_tool(tool_name, args):
            if args.get("collection") == "brand_identities":
                return mock_brand_result
            elif args.get("collection") == "worksheets":
                return mock_ws_result
            raise ValueError(f"Unexpected MCP call: {args}")

        mock_chunk = MagicMock()
        mock_chunk.content = json.dumps(MOCK_PROFILE)

        async def mock_astream(*args, **kwargs):
            yield mock_chunk

        mock_llm = MagicMock()
        mock_llm.astream = mock_astream

        with patch("customer_profile_service.execute_mcp_tool", side_effect=mock_execute_mcp_tool), \
             patch("customer_profile_service.get_ollama_llm", return_value=mock_llm):

            events = []
            async for event in customer_profile_event_generator("brand_123", "English"):
                events.append(event)

            parsed = _collect_events(events)
            types = [e["type"] for e in parsed]

            # Should include: fetching_brand, fetching_worksheet, analyzing, chunk, done
            assert "status" in types
            assert "chunk" in types
            assert "done" in types

            # Verify status progression
            statuses = [e.get("status") for e in parsed if e["type"] == "status"]
            assert "fetching_brand" in statuses
            assert "fetching_worksheet" in statuses
            assert "analyzing" in statuses

            # done event should contain customerProfile
            done_event = next(e for e in parsed if e["type"] == "done")
            assert done_event["customerProfile"]["personaName"] == "Tech-Savvy Tina"
            assert "demographics" in done_event["customerProfile"]

    @pytest.mark.asyncio
    async def test_brand_mcp_failure_emits_error(self):
        """When brand identity MCP fetch fails, should emit an error event."""
        with patch("customer_profile_service.execute_mcp_tool", new_callable=AsyncMock, side_effect=Exception("MCP down")):
            events = []
            async for event in customer_profile_event_generator("bad_id", "English"):
                events.append(event)

            parsed = _collect_events(events)
            error_events = [e for e in parsed if e["type"] == "error"]
            assert len(error_events) >= 1
            assert "Failed to fetch brand identity" in error_events[0]["error"]

    @pytest.mark.asyncio
    async def test_worksheet_mcp_failure_emits_error(self):
        """When worksheet MCP fetch fails, should emit error after brand fetch succeeds."""
        mock_brand_result = MagicMock()
        mock_brand_result.content = [MagicMock(text=json.dumps(MOCK_BRAND))]

        call_count = 0

        async def mock_execute_mcp_tool(tool_name, args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_brand_result
            raise Exception("Worksheet MCP failed")

        with patch("customer_profile_service.execute_mcp_tool", side_effect=mock_execute_mcp_tool):
            events = []
            async for event in customer_profile_event_generator("brand_123", "English"):
                events.append(event)

            parsed = _collect_events(events)
            error_events = [e for e in parsed if e["type"] == "error"]
            assert len(error_events) >= 1
            assert "Failed to fetch worksheet" in error_events[0]["error"]

    @pytest.mark.asyncio
    async def test_no_worksheet_id_emits_error(self):
        """When brand identity has no worksheetId, should emit error."""
        brand_no_ws = {**MOCK_BRAND, "worksheetId": ""}
        mock_brand_result = MagicMock()
        mock_brand_result.content = [MagicMock(text=json.dumps(brand_no_ws))]

        with patch("customer_profile_service.execute_mcp_tool", new_callable=AsyncMock, return_value=mock_brand_result):
            events = []
            async for event in customer_profile_event_generator("brand_123", "English"):
                events.append(event)

            parsed = _collect_events(events)
            error_events = [e for e in parsed if e["type"] == "error"]
            assert len(error_events) >= 1
            assert "no linked worksheet" in error_events[0]["error"]

    @pytest.mark.asyncio
    async def test_invalid_llm_json_emits_error(self):
        """When LLM returns non-JSON, should emit an error event."""
        mock_brand_result = MagicMock()
        mock_brand_result.content = [MagicMock(text=json.dumps(MOCK_BRAND))]
        mock_ws_result = MagicMock()
        mock_ws_result.content = [MagicMock(text=json.dumps(MOCK_WORKSHEET))]

        async def mock_execute_mcp_tool(tool_name, args):
            if args.get("collection") == "brand_identities":
                return mock_brand_result
            return mock_ws_result

        mock_chunk = MagicMock()
        mock_chunk.content = "I don't know how to generate a profile right now."

        async def mock_astream(*args, **kwargs):
            yield mock_chunk

        mock_llm = MagicMock()
        mock_llm.astream = mock_astream

        with patch("customer_profile_service.execute_mcp_tool", side_effect=mock_execute_mcp_tool), \
             patch("customer_profile_service.get_ollama_llm", return_value=mock_llm):

            events = []
            async for event in customer_profile_event_generator("brand_123", "English"):
                events.append(event)

            parsed = _collect_events(events)
            error_events = [e for e in parsed if e["type"] == "error"]
            assert len(error_events) >= 1
            assert "invalid response format" in error_events[0]["error"]
