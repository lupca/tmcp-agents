import json
import logging
import uuid
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage

from variant_generator_agent.graph import variant_generator_graph
from app.utils.sse import sse_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def platform_variants_event_generator(
    master_content_id: str,
    platforms: list[str],
    workspace_id: str,
    language: str = "Vietnamese",
) -> AsyncGenerator[str, None]:
    """
    Wraps the variant_generator_agent graph with SSE streaming.
    Uses astream_events (like chat.py) for real-time transparency.

    Error Strategy: All-or-nothing — the agent's Evaluator and Saver handle abort logic.
    """
    # Validate platforms upfront before even invoking the agent
    valid_platforms = ["facebook", "instagram", "linkedin", "twitter", "tiktok", "youtube", "blog", "email"]
    invalid = [p for p in platforms if p not in valid_platforms]
    if invalid:
        yield sse_event("error", error=f"Invalid platforms: {', '.join(invalid)}")
        return

    initial_state = {
        "messages": [HumanMessage(content=f"Generate platform variants for: {', '.join(platforms)}")],
        "master_content_id": master_content_id,
        "platforms": platforms,
        "workspace_id": workspace_id,
        "language": language,
        "context_data": {},
        "current_platform_index": 0,
        "generated_variants": [],
        "current_variant": None,
        "feedback": "",
        "next_node": "",
    }

    config = {"configurable": {"thread_id": f"var_{uuid.uuid4().hex[:8]}"}}

    try:
        async for event in variant_generator_graph.astream_events(
            initial_state, config=config, version="v2"
        ):
            event_type = event["event"]

            # Node transitions
            if event_type == "on_chain_start":
                name = event.get("name", "")
                if name in ("Retriever", "Evaluator", "Generator", "Saver"):
                    step_desc = {
                        "Retriever": "Fetching master content and context via MCP...",
                        "Evaluator": "Evaluating variant quality...",
                        "Generator": "Generating platform variant with AI...",
                        "Saver": "Saving all variants to database...",
                    }.get(name, name)
                    yield sse_event("status", status="active", agent=name, step=step_desc)

            # LLM starts thinking
            elif event_type == "on_chat_model_start":
                metadata = event.get("metadata", {})
                yield sse_event("status", status="thinking", agent=metadata.get("langgraph_node", "Agent"))

            # LLM streaming tokens
            elif event_type == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield sse_event("chunk", content=chunk.content)

            # MCP tool calls
            elif event_type == "on_tool_start":
                yield sse_event("tool_start", tool=event["name"], input=event["data"].get("input"))

            elif event_type == "on_tool_end":
                output = event["data"].get("output")
                yield sse_event("tool_end", tool=event["name"], output=str(output)[:200])

        # After the graph finishes, get the final state
        final_state = await variant_generator_graph.aget_state(config)
        state_values = final_state.values

        generated_variants = state_values.get("generated_variants", [])
        feedback = state_values.get("feedback", "")

        if generated_variants:
            # Since auto-save is disabled, return full generated variant data for manual review
            variants_data = []
            for v in generated_variants:
                variants_data.append({
                    "platform": v.get("_platform"),
                    "adaptedCopy": v.get("adapted_copy", ""),
                    "hashtags": v.get("hashtags", []),
                    "callToAction": v.get("callToAction", ""),
                    "summary": v.get("summary", ""),
                    "characterCount": v.get("character_count", 0),
                    "platformTips": v.get("platform_tips", ""),
                    "confidenceScore": v.get("confidence_score", 0),
                    "optimizationNotes": v.get("optimization_notes", ""),
                    "seoTitle": v.get("seoTitle", ""),
                    "seoDescription": v.get("seoDescription", ""),
                    "seoKeywords": v.get("seoKeywords", []),
                    "aiPromptUsed": v.get("aiPrompt_used", ""),
                })
            
            yield sse_event(
                "done",
                variants=variants_data,
                platformCount=len(generated_variants),
                feedback=feedback,
            )
        else:
            yield sse_event(
                "error",
                error=feedback or "Failed to generate platform variants.",
                step="Agent execution",
            )

    except Exception as e:
        logger.error(f"Error in variant generator event stream: {e}")
        yield sse_event("error", error=str(e), step="Unexpected error")
