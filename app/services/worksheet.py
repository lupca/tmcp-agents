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
        def _mcp_args(collection: str, record_id: str) -> dict:
            args = {"collection": collection, "record_id": record_id}
            if auth_token:
                args["auth_token"] = auth_token
            return args

        import asyncio

        # Build fetch tasks for Brands
        brand_tasks = []
        if brand_ids:
            yield sse_event("status", status="fetching_brands", agent="MarketingStrategist")
            for bid in brand_ids:
                brand_tasks.append(execute_mcp_tool("get_record", _mcp_args("brand_identities", bid)))

        # Build fetch tasks for Customers
        customer_tasks = []
        if customer_ids:
            yield sse_event("status", status="fetching_customers", agent="MarketingStrategist")
            for cid in customer_ids:
                customer_tasks.append(execute_mcp_tool("get_record", _mcp_args("customer_personas", cid)))

        # Execute all tasks concurrently
        all_tasks = brand_tasks + customer_tasks
        brand_contexts = []
        customer_contexts = []

        if all_tasks:
            results = await asyncio.gather(*all_tasks, return_exceptions=True)

            # Process results matching original list order
            for i, result in enumerate(results):
                is_brand = i < len(brand_tasks)
                task_id = brand_ids[i] if is_brand else customer_ids[i - len(brand_tasks)]

                if isinstance(result, Exception):
                    type_str = "brand" if is_brand else "customer"
                    logger.warning(f"Failed to fetch {type_str} {task_id}: {result}")
                else:
                    try:
                        parsed = json.loads(result.content[0].text)
                        if is_brand:
                            brand_contexts.append(parsed)
                        else:
                            customer_contexts.append(parsed)
                    except Exception as e:
                        type_str = "brand" if is_brand else "customer"
                        logger.warning(f"Failed to parse {type_str} {task_id}: {e}")

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
