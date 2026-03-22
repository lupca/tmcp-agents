import logging
import json
import asyncio
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
        def _mcp_args(collection: str, record_id: str) -> dict:
            args = {"collection": collection, "record_id": record_id}
            if auth_token:
                args["auth_token"] = auth_token
            return args

        # Fetch Brands & Customers Concurrently
        if brand_ids:
            yield sse_event("status", status="fetching_brands", agent="MarketingStrategist")
        if customer_ids:
            yield sse_event("status", status="fetching_customers", agent="MarketingStrategist")

        async def fetch_record(collection: str, record_id: str):
            res = await execute_mcp_tool("get_record", _mcp_args(collection, record_id))
            return json.loads(res.content[0].text)

        brand_tasks = [fetch_record("brand_identities", bid) for bid in (brand_ids or [])]
        customer_tasks = [fetch_record("customer_personas", cid) for cid in (customer_ids or [])]

        brand_results = await asyncio.gather(*brand_tasks, return_exceptions=True)
        customer_results = await asyncio.gather(*customer_tasks, return_exceptions=True)

        brand_contexts = []
        for i, res in enumerate(brand_results):
            if isinstance(res, Exception):
                logger.warning(f"Failed to fetch brand {(brand_ids or [])[i]}: {res}")
            else:
                brand_contexts.append(res)

        customer_contexts = []
        for i, res in enumerate(customer_results):
            if isinstance(res, Exception):
                logger.warning(f"Failed to fetch customer {(customer_ids or [])[i]}: {res}")
            else:
                customer_contexts.append(res)

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
