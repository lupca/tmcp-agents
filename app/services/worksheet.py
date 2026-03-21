import logging
import json
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm_factory import get_ollama_llm
from marketing_team.prompts import WORKSHEET_PROMPT
from app.utils.sse import sse_event
from app.tools.mcp_bridge import execute_mcp_tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def worksheet_event_generator(
    brand_ids: list[str],
    customer_ids: list[str],
    language: str = "Vietnamese",
    auth_token: str = "",
) -> AsyncGenerator[str, None]:
    """
    Generates SSE events for worksheet creation using a direct LLM call.
    """
    try:
        import asyncio

        def _mcp_args(collection: str, record_id: str) -> dict:
            args = {"collection": collection, "record_id": record_id}
            if auth_token:
                args["auth_token"] = auth_token
            return args

        async def fetch_record(collection: str, record_id: str) -> dict | None:
            try:
                res = await execute_mcp_tool("get_record", _mcp_args(collection, record_id))
                return json.loads(res.content[0].text)
            except Exception as e:
                logger.warning(f"Failed to fetch {collection} {record_id}: {e}")
                return None

        brand_contexts = []
        customer_contexts = []

        # Fetch Brands
        if brand_ids:
            yield sse_event("status", status="fetching_brands", agent="MarketingStrategist")
            brand_tasks = [fetch_record("brand_identities", bid) for bid in brand_ids]
            results = await asyncio.gather(*brand_tasks)
            brand_contexts = [r for r in results if r is not None]

        # Fetch Customers
        if customer_ids:
            yield sse_event("status", status="fetching_customers", agent="MarketingStrategist")
            customer_tasks = [fetch_record("customer_personas", cid) for cid in customer_ids]
            results = await asyncio.gather(*customer_tasks)
            customer_contexts = [r for r in results if r is not None]

        yield sse_event("status", status="thinking", agent="MarketingStrategist")

        brand_context_str = json.dumps(brand_contexts, ensure_ascii=False, indent=2) if brand_contexts else "No specific brand data provided."
        customer_context_str = json.dumps(customer_contexts, ensure_ascii=False, indent=2) if customer_contexts else "No specific customer data provided."

        llm = get_ollama_llm(temperature=0.7)

        prompt = WORKSHEET_PROMPT.format(
            brandContext=brand_context_str,
            customerContext=customer_context_str,
            language=language,
        )

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Please generate the Strategic Worksheet now based on the provided context."),
        ]

        # Stream tokens
        full_content = ""
        async for chunk in llm.astream(messages):
            if chunk.content:
                full_content += chunk.content
                yield sse_event("chunk", content=chunk.content)

        yield sse_event("done", worksheet=full_content)

    except Exception as e:
        logger.error(f"Error in worksheet generator: {e}")
        yield sse_event("error", error=str(e))
