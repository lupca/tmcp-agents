import sys
import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from marketing_strategy_service import marketing_strategy_event_generator
from llm_utils import parse_json_response

def _collect_events(raw_events):
    """Parse SSE event strings into dicts."""
    events = []
    for e in raw_events:
        if e.startswith("data: "):
            events.append(json.loads(e[6:].strip()))
    return events

# --- MOCK DATA ---
MOCK_WORKSHEET = {
    "title": "Modern Cafe Worksheet",
    "content": "A cozy cafe in downtown Seattle focusing on remote workers and high-quality coffee.",
}

MOCK_BRAND = {
    "brandName": "Nebula Brew",
    "missionStatement": "Fueling creativity one cup at a time.",
    "keywords": ["creative", "focus", "quality"],
}

MOCK_ICP = {
    "personaName": "Freelancer Fiona",
    "summary": "Fiona is a 28-year-old graphic designer who needs a quiet place to work.",
    "goalsAndMotivations": {"primary": "Productivity", "secondary": "Networking"},
    "painPointsAndChallenges": {"primary": "Noisy environments", "secondary": "Bad wifi"},
    "psychographics": {"interests": ["Design", "Tech", "Coffee"]},
}

MOCK_STRATEGY = {
    "acquisitionStrategy": "Partner with local coworking spaces and run Instagram ads targeting freelancers.",
    "positioning": "For Freelancer Fiona, Nebula Brew is the one Cafe that offers a productivity sanctuary.",
    "valueProposition": "Your office away from the office, with better coffee.",
    "toneOfVoice": "Inspiring, Calm, Professional.",
}

class TestMarketingStrategyService:
    @pytest.mark.asyncio
    async def test_successful_generation(self):
        """Full happy path: fetch 3 resources -> LLM -> JSON -> done."""
        
        # Mock MCP results
        mock_ws_result = MagicMock()
        mock_ws_result.content = [MagicMock(text=json.dumps(MOCK_WORKSHEET))]
        
        mock_brand_result = MagicMock()
        mock_brand_result.content = [MagicMock(text=json.dumps(MOCK_BRAND))]
        
        mock_icp_result = MagicMock()
        mock_icp_result.content = [MagicMock(text=json.dumps(MOCK_ICP))]

        # Mock execute_mcp_tool to return different things based on collection
        async def mock_execute_mcp_tool(tool_name, args):
            if tool_name != "get_record":
                raise ValueError(f"Expected tool 'get_record', got {tool_name}")
            collection = args.get("collection")
            if collection == "worksheets":
                return mock_ws_result
            elif collection == "brand_identities":
                return mock_brand_result
            elif collection == "ideal_customer_profiles":
                return mock_icp_result
            raise ValueError(f"Unexpected collection: {collection}")

        # Mock LLM
        mock_chunk = MagicMock()
        mock_chunk.content = json.dumps(MOCK_STRATEGY)
        
        async def mock_astream(*args, **kwargs):
            yield mock_chunk
        
        mock_llm = MagicMock()
        mock_llm.astream = mock_astream

        with patch("marketing_strategy_service.execute_mcp_tool", side_effect=mock_execute_mcp_tool), \
             patch("marketing_strategy_service.get_ollama_llm", return_value=mock_llm):

            events = []
            async for event in marketing_strategy_event_generator(
                worksheet_id="ws_1",
                brand_identity_id="bi_1",
                customer_profile_id="icp_1",
                goal="Increase foot traffic",
                language="English"
            ):
                events.append(event)

            parsed = _collect_events(events)
            
            # Check status progression
            statuses = [e.get("status") for e in parsed if e["type"] == "status"]
            assert "fetching_worksheet" in statuses
            assert "fetching_brand" in statuses
            assert "fetching_icp" in statuses
            assert "analyzing" in statuses

            # Check done event
            done_event = next(e for e in parsed if e["type"] == "done")
            strategy = done_event["marketingStrategy"]
            assert strategy["positioning"] == MOCK_STRATEGY["positioning"]

    @pytest.mark.asyncio
    async def test_mcp_failure_handles_gracefully(self):
        """If one MCP call fails, it should emit an error."""
        with patch("marketing_strategy_service.execute_mcp_tool", side_effect=Exception("Database down")):
            events = []
            async for event in marketing_strategy_event_generator("ws", "bi", "icp"):
                events.append(event)
            
            parsed = _collect_events(events)
            error = next(e for e in parsed if e["type"] == "error")
            assert "Failed to fetch worksheet" in error["error"]

    @pytest.mark.asyncio
    async def test_invalid_llm_json(self):
        """If LLM returns bad JSON, emit error."""
        # Setup successful MCP calls
        mock_ws_result = MagicMock()
        mock_ws_result.content = [MagicMock(text=json.dumps(MOCK_WORKSHEET))]
        mock_brand_result = MagicMock()
        mock_brand_result.content = [MagicMock(text=json.dumps(MOCK_BRAND))]
        mock_icp_result = MagicMock()
        mock_icp_result.content = [MagicMock(text=json.dumps(MOCK_ICP))]

        async def mock_execute(*args, **kwargs):
            return mock_ws_result # Simplified: return same structure for all, works for this test

        # Setup Bad LLM response
        mock_chunk = MagicMock()
        mock_chunk.content = "Not JSON at all"
        
        async def mock_astream(*args, **kwargs):
            yield mock_chunk
            
        mock_llm = MagicMock()
        mock_llm.astream = mock_astream

        with patch("marketing_strategy_service.execute_mcp_tool", return_value=mock_ws_result), \
             patch("marketing_strategy_service.get_ollama_llm", return_value=mock_llm):
             
            events = []
            async for event in marketing_strategy_event_generator("ws", "bi", "icp"):
                events.append(event)
                
            parsed = _collect_events(events)
            error = next(e for e in parsed if e["type"] == "error")
            assert "not valid JSON" in error["error"]
