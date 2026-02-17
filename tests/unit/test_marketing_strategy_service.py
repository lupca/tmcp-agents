import sys
import os
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Define mocks
mock_langchain_core = MagicMock()
mock_messages = MagicMock()
mock_tools = MagicMock()
mock_mcp = MagicMock()
mock_mcp_client = MagicMock()
mock_stdio = MagicMock()
mock_sse = MagicMock()
mock_ollama = MagicMock()

modules_to_patch = {
    "langchain_core": mock_langchain_core,
    "langchain_core.messages": mock_messages,
    "langchain_core.tools": mock_tools,
    "mcp": mock_mcp,
    "mcp.client": mock_mcp_client,
    "mcp.client.stdio": mock_stdio,
    "mcp.client.sse": mock_sse,
    "langchain_ollama": mock_ollama,
}

# Add path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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
    def test_successful_generation(self):
        """Full happy path: fetch 3 resources -> LLM -> JSON -> done."""
        asyncio.run(self._test_successful_generation_async())

    async def _test_successful_generation_async(self):
        with patch.dict(sys.modules, modules_to_patch):
            # Import inside patch context
            if "app.services.strategy" in sys.modules:
                del sys.modules["app.services.strategy"]
            from app.services.strategy import marketing_strategy_event_generator

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

            with patch("app.services.strategy.execute_mcp_tool", side_effect=mock_execute_mcp_tool), \
                 patch("app.services.strategy.get_ollama_llm", return_value=mock_llm):

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
                assert "fetching_context" in statuses
                assert "analyzing" in statuses

                # Check done event
                done_event = next(e for e in parsed if e["type"] == "done")
                strategy = done_event["marketingStrategy"]
                assert strategy["positioning"] == MOCK_STRATEGY["positioning"]

    def test_mcp_failure_handles_gracefully(self):
        """If one MCP call fails, it should emit an error."""
        asyncio.run(self._test_mcp_failure_handles_gracefully_async())

    async def _test_mcp_failure_handles_gracefully_async(self):
        with patch.dict(sys.modules, modules_to_patch):
            if "app.services.strategy" in sys.modules:
                del sys.modules["app.services.strategy"]
            from app.services.strategy import marketing_strategy_event_generator
            
            with patch("app.services.strategy.execute_mcp_tool", side_effect=Exception("Database down")):
                events = []
                async for event in marketing_strategy_event_generator("ws", "bi", "icp"):
                    events.append(event)

                parsed = _collect_events(events)
                error = next(e for e in parsed if e["type"] == "error")
                assert "Failed to fetch" in error["error"] or "Database down" in error["error"]

    def test_invalid_llm_json(self):
        """If LLM returns bad JSON, emit error."""
        asyncio.run(self._test_invalid_llm_json_async())

    async def _test_invalid_llm_json_async(self):
        with patch.dict(sys.modules, modules_to_patch):
            if "app.services.strategy" in sys.modules:
                del sys.modules["app.services.strategy"]
            from app.services.strategy import marketing_strategy_event_generator
            
            # Setup successful MCP calls
            mock_ws_result = MagicMock()
            mock_ws_result.content = [MagicMock(text=json.dumps(MOCK_WORKSHEET))]
            mock_brand_result = MagicMock()
            mock_brand_result.content = [MagicMock(text=json.dumps(MOCK_BRAND))]
            mock_icp_result = MagicMock()
            mock_icp_result.content = [MagicMock(text=json.dumps(MOCK_ICP))]

            async def mock_execute(*args, **kwargs):
                return mock_ws_result

            # Setup Bad LLM response
            mock_chunk = MagicMock()
            mock_chunk.content = "Not JSON at all"

            async def mock_astream(*args, **kwargs):
                yield mock_chunk
                
            mock_llm = MagicMock()
            mock_llm.astream = mock_astream

            with patch("app.services.strategy.execute_mcp_tool", return_value=mock_ws_result), \
                 patch("app.services.strategy.get_ollama_llm", return_value=mock_llm):

                events = []
                async for event in marketing_strategy_event_generator("ws", "bi", "icp"):
                    events.append(event)

                parsed = _collect_events(events)
                error = next(e for e in parsed if e["type"] == "error")
                assert "not valid JSON" in error["error"]

if __name__ == "__main__":
    t = TestMarketingStrategyService()
    t.test_successful_generation()
    t.test_mcp_failure_handles_gracefully()
    t.test_invalid_llm_json()
    print("All tests passed!")
