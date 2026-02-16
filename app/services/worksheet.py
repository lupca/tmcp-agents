import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm_factory import get_ollama_llm
from marketing_team.prompts import WORKSHEET_PROMPT
from app.utils.sse import sse_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def worksheet_event_generator(
    business_description: str,
    target_audience: str,
    pain_points: str,
    usp: str,
    language: str = "Vietnamese",
) -> AsyncGenerator[str, None]:
    """
    Generates SSE events for worksheet creation using a direct LLM call.
    """
    try:
        yield sse_event("status", status="thinking", agent="BusinessConsultant")

        llm = get_ollama_llm(temperature=0.7)

        prompt = WORKSHEET_PROMPT.format(
            businessDescription=business_description,
            targetAudience=target_audience,
            painPoints=pain_points,
            uniqueSellingProposition=usp,
            language=language,
        )

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Please generate the business definition worksheet now."),
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
