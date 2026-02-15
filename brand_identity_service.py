import json
import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from llm_factory import get_ollama_llm
from marketing_team.prompts import BRAND_IDENTITY_PROMPT
from mcp_bridge import execute_mcp_tool
from sse import sse_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def brand_identity_event_generator(
    worksheet_id: str,
    language: str = "Vietnamese",
) -> AsyncGenerator[str, None]:
    """
    Generates SSE events for brand identity creation.

    Flow:
    1. Fetch worksheet content via MCP
    2. Build prompt with worksheet content + language
    3. Stream LLM tokens
    4. Parse JSON result and emit done event
    """
    try:
        # --- Step 1: Fetch worksheet via MCP ---
        yield sse_event("status", status="fetching_worksheet", agent="BrandExpert")

        try:
            result = await execute_mcp_tool(
                "get_record",
                {"collection": "worksheets", "record_id": worksheet_id},
            )
            worksheet_data = result.content[0].text
        except Exception as e:
            logger.error(f"MCP fetch failed: {e}")
            yield sse_event("error", error=f"Failed to fetch worksheet: {e}")
            return

        # Extract the content field from worksheet JSON
        try:
            ws_parsed = json.loads(worksheet_data)
            worksheet_content = ws_parsed.get("content", "") or ws_parsed.get("title", "")
            if not worksheet_content:
                # Fallback: use full JSON as context
                worksheet_content = worksheet_data
        except (json.JSONDecodeError, TypeError):
            worksheet_content = worksheet_data

        # --- Step 2: Build prompt and call LLM ---
        yield sse_event("status", status="analyzing", agent="BrandExpert")

        llm = get_ollama_llm(temperature=0.7)

        prompt = BRAND_IDENTITY_PROMPT.format(
            worksheetContent=worksheet_content,
            language=language,
        )

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(
                content="Please generate the brand identity based on the worksheet now."
            ),
        ]

        # --- Step 3: Stream tokens ---
        full_content = ""
        async for chunk in llm.astream(messages):
            if chunk.content:
                full_content += chunk.content
                yield sse_event("chunk", content=chunk.content)

        # --- Step 4: Parse JSON and emit done ---
        try:
            brand_data = _parse_json_response(full_content)
            yield sse_event("done", brandIdentity=brand_data)
        except ValueError as e:
            logger.error(f"JSON parsing failed: {e}")
            yield sse_event(
                "error",
                error="AI returned an invalid response format. Please try again.",
            )

    except Exception as e:
        logger.error(f"Error in brand identity generator: {e}")
        yield sse_event("error", error=str(e))


def _parse_json_response(text: str) -> dict:
    """Extract and parse JSON from an LLM response that may contain extra text."""
    # Try direct parse first
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block within markdown code fences
    if "```" in stripped:
        for block in stripped.split("```"):
            block = block.strip()
            if block.startswith("json"):
                block = block[4:].strip()
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue

    # Try to find JSON by matching braces
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response: {stripped[:200]}")
