import json
import os
import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WORKSHEET_PROMPT = """
**Persona:** You are an expert business consultant and strategist. Your talent is to take raw ideas and synthesize them into a clear, structured, and actionable business definition document.

**Task:** Generate a comprehensive "Define Your Business & Target Audience" worksheet based on the user's initial inputs.

**Context:**
The user has provided the following core concepts for their business:
- **Business Description:** {businessDescription}
- **Target Audience:** {targetAudience}
- **Customer Pain Points:** {painPoints}
- **Unique Selling Proposition (USP):** {uniqueSellingProposition}

**Instructions & Rules:**
1.  **Language:** All generated content MUST be in the specified language: **{language}**.
2.  **Synthesize and Expand:** Do not just repeat the user's input. Synthesize the information and expand upon it to create a coherent and insightful document.
3.  **Structure the Worksheet:** Format the output as a clean, well-organized worksheet using Markdown. Use clear headings for each section (e.g., "Business Definition," "Ideal Target Audience," "Core Problems We Solve," "Our Unique Advantage").
4.  **Clarity and Readability:** Use simple, professional language. The final worksheet should be easy for a business owner to read, understand, and use as a foundational document.
5.  **Output Format:** Return ONLY the formatted worksheet content in Markdown. Do not wrap it in code blocks or any other container.
"""


def _get_llm():
    """Get the best available LLM - prefer Google Gemini, fallback to Ollama."""
    # google_api_key = os.getenv("GOOGLE_API_KEY")
    # if google_api_key:
    #     try:
    #         from langchain_google_genai import ChatGoogleGenerativeAI
    #         return ChatGoogleGenerativeAI(
    #             model="gemini-2.0-flash",
    #             google_api_key=google_api_key,
    #             temperature=0.7,
    #         )
    #     except ImportError:
    #         logger.warning("langchain-google-genai not installed, falling back to Ollama")

    from langchain_ollama import ChatOllama
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://172.20.10.8:11434")
    return ChatOllama(model="qwen2.5", temperature=0.7, base_url=ollama_base_url)


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
        # Status: thinking
        yield f"data: {json.dumps({'type': 'status', 'status': 'thinking', 'agent': 'BusinessConsultant'})}\n\n"

        llm = _get_llm()

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
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk.content})}\n\n"

        # Done
        yield f"data: {json.dumps({'type': 'done', 'worksheet': full_content})}\n\n"

    except Exception as e:
        logger.error(f"Error in worksheet generator: {e}")
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
