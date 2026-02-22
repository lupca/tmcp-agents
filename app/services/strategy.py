import json
import asyncio
from typing import AsyncGenerator, Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage 
from app.tools.mcp_bridge import execute_mcp_tool

from app.core.llm_factory import get_ollama_llm
from marketing_team.prompts import MARKETING_STRATEGY_PROMPT
from app.utils.sse import sse_event
from app.utils.llm import parse_json_response

async def marketing_strategy_event_generator(
    worksheet_id: str,
    brand_identity_id: str,
    customer_profile_id: str,
    goal: str = "",
    language: str = "Vietnamese",
    auth_token: str = "",
) -> AsyncGenerator[str, None]:
    """
    Orchestrate the AI agent to generate a Marketing Strategy.
    Fetches Worksheet + Brand + ICP via MCP, then streams LLM output.
    """
    try:
        # --- Step 1: Fetch all contexts ---

        def _mcp_args(collection: str, record_id: str) -> dict:
            args = {"collection": collection, "record_id": record_id}
            if auth_token:
                args["auth_token"] = auth_token
            return args

        # 1. Fetch All Context (Parallel)
        # We start all fetches immediately to run in parallel, significantly reducing total latency.
        # We yield status events sequentially to preserve the API contract for the frontend.

        async def fetch_worksheet():
            try:
                ws_result = await execute_mcp_tool("get_record", _mcp_args("worksheets", worksheet_id))
                ws_data_raw = ws_result.content[0].text
                ws_parsed = json.loads(ws_data_raw)
                return ws_parsed.get("content", "")
            except Exception as e:
                raise Exception(f"Failed to fetch worksheet: {str(e)}")

        async def fetch_brand():
            try:
                brand_result = await execute_mcp_tool("get_record", _mcp_args("brand_identities", brand_identity_id))
                brand_data_raw = brand_result.content[0].text
                return json.loads(brand_data_raw)
            except Exception as e:
                raise Exception(f"Failed to fetch brand identity: {str(e)}")

        async def fetch_icp():
            try:
                icp_result = await execute_mcp_tool("get_record", _mcp_args("customer_personas", customer_profile_id))
                icp_data_raw = icp_result.content[0].text
                return json.loads(icp_data_raw)
            except Exception as e:
                raise Exception(f"Failed to fetch customer profile: {str(e)}")

        # Start tasks in parallel
        task_worksheet = asyncio.create_task(fetch_worksheet())
        task_brand = asyncio.create_task(fetch_brand())
        task_icp = asyncio.create_task(fetch_icp())

        try:
            yield sse_event("status", status="fetching_worksheet", agent="MarketingStrategist")
            worksheet_content = await task_worksheet

            yield sse_event("status", status="fetching_brand", agent="MarketingStrategist")
            brand_parsed = await task_brand

            yield sse_event("status", status="fetching_icp", agent="MarketingStrategist")
            icp_parsed = await task_icp

        except Exception as e:
            yield sse_event("error", error=str(e))
            return

        # --- Step 4: Build Prompt ---
        yield sse_event("status", status="analyzing", agent="MarketingStrategist")

        # Format custom prompt section if goal is present
        custom_prompt_section = ""
        if goal:
            custom_prompt_section = f"""
4.  **Specific User Request:**
    ---
    The user has provided a specific focus. Prioritize this request in your output: "{goal}"
    ---
"""

        core_messaging = brand_parsed.get("core_messaging", {})
        psychographics = icp_parsed.get("psychographics", {})

        # Ensure JSON fields are strings for prompt injection
        prompt = MARKETING_STRATEGY_PROMPT.format(
            worksheetContent=worksheet_content,
            brandName=brand_parsed.get("brand_name", "") or brand_parsed.get("brandName", ""),
            missionStatement=core_messaging.get("mission_statement", ""),
            keywords=json.dumps(core_messaging.get("keywords", [])),
            personaName=icp_parsed.get("persona_name", "") or icp_parsed.get("personaName", ""),
            icpSummary=icp_parsed.get("summary", ""),
            goals=json.dumps(psychographics.get("goals", [])),
            painPoints=json.dumps(psychographics.get("pain_points", [])),
            interests=json.dumps(psychographics),
            customPromptSection=custom_prompt_section,
            language=language
        )
        
        # Helper to safely dump if it's a dict, else return as is
        def safe_dump(val):
            return json.dumps(val) if isinstance(val, (dict, list)) else str(val)

        # Re-formatting with safe dumps
        prompt = MARKETING_STRATEGY_PROMPT.format(
            worksheetContent=worksheet_content,
            brandName=brand_parsed.get("brand_name", "") or brand_parsed.get("brandName", ""),
            missionStatement=core_messaging.get("mission_statement", ""),
            keywords=safe_dump(core_messaging.get("keywords", [])),
            personaName=icp_parsed.get("persona_name", "") or icp_parsed.get("personaName", ""),
            icpSummary=icp_parsed.get("summary", ""),
            goals=safe_dump(psychographics.get("goals", [])),
            painPoints=safe_dump(psychographics.get("pain_points", [])),
            interests=safe_dump(psychographics),
            customPromptSection=custom_prompt_section,
            language=language
        )

        llm = get_ollama_llm(temperature=0.7)
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Generate the marketing strategy based on the above context.")
        ]

        # --- Step 5: Stream Tokens ---
        full_content = ""
        async for chunk in llm.astream(messages):
            full_content += chunk.content
            yield sse_event("chunk", content=chunk.content)

        # --- Step 6: Finalize (Parse JSON) ---
        try:
            strategy_data = parse_json_response(full_content)
            yield sse_event("done", marketingStrategy=strategy_data)
        except ValueError as e:
            yield sse_event("error", error=f"Generated content was not valid JSON: {str(e)}")

    except Exception as e:
        yield sse_event("error", error=str(e))
