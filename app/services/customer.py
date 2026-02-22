import json
import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm_factory import get_ollama_llm
from app.utils.llm import parse_json_response
from marketing_team.prompts import CUSTOMER_PROFILE_PROMPT
from app.tools.mcp_bridge import execute_mcp_tool
from app.utils.sse import sse_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def customer_profile_event_generator(
    brand_identity_id: str,
    language: str = "Vietnamese",
    auth_token: str = "",
) -> AsyncGenerator[str, None]:
    """
    Generates SSE events for ideal customer profile creation.

    Flow:
    1. Fetch brand identity via MCP (using user's auth token)
    2. Build prompt with brand data
    3. Stream LLM tokens
    4. Parse JSON result and emit done event
    """
    try:
        # --- Step 1: Fetch brand identity via MCP ---
        yield sse_event("status", status="fetching_brand", agent="MarketResearcher")

        try:
            mcp_args = {"collection": "brand_identities", "record_id": brand_identity_id}
            if auth_token:
                mcp_args["auth_token"] = auth_token
            result = await execute_mcp_tool("get_record", mcp_args)
            brand_data_raw = result.content[0].text
        except Exception as e:
            logger.error(f"MCP fetch brand identity failed: {e}")
            yield sse_event("error", error=f"Failed to fetch brand identity: {e}")
            return

        # Parse brand identity
        try:
            brand_parsed = json.loads(brand_data_raw)
        except (json.JSONDecodeError, TypeError):
            yield sse_event("error", error="Failed to parse brand identity data.")
            return

        # --- Step 2: Build prompt and call LLM ---
        yield sse_event("status", status="analyzing", agent="MarketResearcher")

        llm = get_ollama_llm(temperature=0.7)

        core_messaging = brand_parsed.get("core_messaging", {})
        visual_assets = brand_parsed.get("visual_assets", {})

        prompt = CUSTOMER_PROFILE_PROMPT.format(
            brandName=brand_parsed.get("brand_name", "") or brand_parsed.get("name", ""),
            slogan=core_messaging.get("slogan", "") or core_messaging.get("mission_statement", ""),
            missionStatement=core_messaging.get("mission_statement", ""),
            keywords=json.dumps(core_messaging.get("keywords", []), ensure_ascii=False),
            voiceTone=brand_parsed.get("voice_and_tone", ""),
            targetAudience="", # No direct equivalent column in new schema
            colors=json.dumps(visual_assets.get("color_palette", []), ensure_ascii=False),
            language=language,
        )

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(
                content="Please generate the ideal customer profile based on the brand identity and worksheet now."
            ),
        ]

        # --- Step 4: Stream tokens ---
        full_content = ""
        async for chunk in llm.astream(messages):
            if chunk.content:
                full_content += chunk.content
                yield sse_event("chunk", content=chunk.content)

        # --- Step 5: Parse JSON and emit done ---
        try:
            profile_data = parse_json_response(full_content)
            yield sse_event("done", customerProfile=profile_data)
        except ValueError as e:
            logger.error(f"JSON parsing failed: {e}")
            yield sse_event(
                "error",
                error="AI returned an invalid response format. Please try again.",
            )

    except Exception as e:
        logger.error(f"Error in customer profile generator: {e}")
        yield sse_event("error", error=str(e))
