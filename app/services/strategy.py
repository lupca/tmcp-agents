import json
import asyncio
from typing import AsyncGenerator, Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
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
) -> AsyncGenerator[str, None]:
    """
    Orchestrate the AI agent to generate a Marketing Strategy.
    Fetches Worksheet + Brand + ICP via MCP, then streams LLM output.
    """
    try:
        # --- Step 1: Fetch all contexts in parallel ---
        yield sse_event("status", status="fetching_context", agent="MarketingStrategist")

        async def fetch_worksheet():
            try:
                res = await execute_mcp_tool("get_record", {"collection": "worksheets", "record_id": worksheet_id})
                data = json.loads(res.content[0].text)
                return data.get("content", "")
            except Exception as e:
                raise Exception(f"Failed to fetch worksheet: {e}")

        async def fetch_brand():
            try:
                res = await execute_mcp_tool("get_record", {"collection": "brand_identities", "record_id": brand_identity_id})
                return json.loads(res.content[0].text)
            except Exception as e:
                raise Exception(f"Failed to fetch brand identity: {e}")

        async def fetch_icp():
            try:
                res = await execute_mcp_tool("get_record", {"collection": "ideal_customer_profiles", "record_id": customer_profile_id})
                return json.loads(res.content[0].text)
            except Exception as e:
                raise Exception(f"Failed to fetch customer profile: {e}")

        try:
            worksheet_content, brand_parsed, icp_parsed = await asyncio.gather(
                fetch_worksheet(),
                fetch_brand(),
                fetch_icp()
            )
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

        # Ensure JSON fields are strings for prompt injection
        prompt = MARKETING_STRATEGY_PROMPT.format(
            worksheetContent=worksheet_content,
            brandName=brand_parsed.get("brandName", ""),
            missionStatement=brand_parsed.get("missionStatement", ""),
            keywords=json.dumps(brand_parsed.get("keywords", [])),
            personaName=icp_parsed.get("personaName", ""),
            icpSummary=icp_parsed.get("summary", ""),
            goals=icp_parsed.get("goalsAndMotivations", ""), # Already stringified JSON in DB usually, but let's check. 
            # In DB, JSON fields are stored as JSON. mcp read_resource returns JSON string.
            # verify if icp_parsed['goalsAndMotivations'] is dict or string?
            # PocketBase returns JSON fields as dicts. So we need to dump them.
            painPoints=json.dumps(icp_parsed.get("painPointsAndChallenges", {})), # using dump just in case it's a dict
            interests=json.dumps(icp_parsed.get("psychographics", {}).get("interests", "")), # accessing nested
            # Wait, prompts.py expects {interests}.
            # The prompt says: Interests: {interests}
            # icp_parsed['psychographics'] is a dict (or string JSON).
            customPromptSection=custom_prompt_section,
            language=language
        )
        
        # Helper to safely dump if it's a dict, else return as is
        def safe_dump(val):
            return json.dumps(val) if isinstance(val, (dict, list)) else str(val)

        # Re-formatting with safe dumps
        prompt = MARKETING_STRATEGY_PROMPT.format(
            worksheetContent=worksheet_content,
            brandName=brand_parsed.get("brandName", ""),
            missionStatement=brand_parsed.get("missionStatement", ""),
            keywords=safe_dump(brand_parsed.get("keywords", [])),
            personaName=icp_parsed.get("personaName", ""),
            icpSummary=icp_parsed.get("summary", ""),
            goals=safe_dump(icp_parsed.get("goalsAndMotivations", {})),
            painPoints=safe_dump(icp_parsed.get("painPointsAndChallenges", {})),
            interests=safe_dump(icp_parsed.get("psychographics", {})), # Just dump the whole psychographics object or specific field? Prompt said {interests}. I'll dump whole psychographics for context.
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
