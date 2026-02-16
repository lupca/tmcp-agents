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
) -> AsyncGenerator[str, None]:
    """
    Generates SSE events for ideal customer profile creation.

    Flow:
    1. Fetch brand identity via MCP
    2. Fetch linked worksheet via MCP
    3. Build prompt with brand + worksheet data
    4. Stream LLM tokens
    5. Parse JSON result and emit done event
    """
    try:
        # --- Step 1: Fetch brand identity via MCP ---
        yield sse_event("status", status="fetching_brand", agent="MarketResearcher")

        try:
            result = await execute_mcp_tool(
                "get_record",
                {"collection": "brand_identities", "record_id": brand_identity_id},
            )
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

        # --- Step 2: Fetch linked worksheet via MCP ---
        worksheet_id = brand_parsed.get("worksheetId", "")
        if not worksheet_id:
            yield sse_event("error", error="Brand identity has no linked worksheet.")
            return

        yield sse_event("status", status="fetching_worksheet", agent="MarketResearcher")

        try:
            result = await execute_mcp_tool(
                "get_record",
                {"collection": "worksheets", "record_id": worksheet_id},
            )
            worksheet_data_raw = result.content[0].text
        except Exception as e:
            logger.error(f"MCP fetch worksheet failed: {e}")
            yield sse_event("error", error=f"Failed to fetch worksheet: {e}")
            return

        # Extract worksheet content
        try:
            ws_parsed = json.loads(worksheet_data_raw)
            worksheet_content = ws_parsed.get("content", "") or ws_parsed.get("title", "")
            if not worksheet_content:
                worksheet_content = worksheet_data_raw
        except (json.JSONDecodeError, TypeError):
            worksheet_content = worksheet_data_raw

        # --- Step 3: Build prompt and call LLM ---
        yield sse_event("status", status="analyzing", agent="MarketResearcher")

        llm = get_ollama_llm(temperature=0.7)

        prompt = CUSTOMER_PROFILE_PROMPT.format(
            worksheetContent=worksheet_content,
            brandName=brand_parsed.get("brandName", ""),
            slogan=brand_parsed.get("slogan", ""),
            missionStatement=brand_parsed.get("missionStatement", ""),
            keywords=json.dumps(brand_parsed.get("keywords", []), ensure_ascii=False),
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
