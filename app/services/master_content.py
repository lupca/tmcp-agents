import json
import logging
import uuid
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage

from master_content_agent.graph import master_content_graph
from app.utils.sse import sse_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def master_content_event_generator(
    campaign_id: str,
    workspace_id: str,
    language: str = "Vietnamese",
    auth_token: str = "",
) -> AsyncGenerator[str, None]:
    from app.tools.mcp_bridge import auth_token_var
    auth_token_var.set(auth_token)
    """
    Wraps the master_content_agent graph with SSE streaming.
    Uses astream_events (like chat.py) for real-time transparency.
    """
    initial_state = {
        "messages": [HumanMessage(content="Generate master content for this campaign.")],
        "campaign_id": campaign_id,
        "workspace_id": workspace_id,
        "language": language,
        "angle_context": None,
        "context_data": {},
        "generated_content": None,
        "feedback": "",
        "next_node": "",
    }

    config = {"configurable": {"thread_id": f"mc_{uuid.uuid4().hex[:8]}"}}

    try:
        async for event in master_content_graph.astream_events(
            initial_state, config=config, version="v2"
        ):
            event_type = event["event"]

            # Node transitions → status events
            if event_type == "on_chain_start":
                name = event.get("name", "")
                if name in ("Retriever", "Evaluator", "Generator", "Saver"):
                    step_desc = {
                        "Retriever": "Fetching campaign, brand, persona context via MCP...",
                        "Evaluator": "Evaluating quality...",
                        "Generator": "Generating master content with AI...",
                        "Saver": "Saving to database...",
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

        # After graph finishes, get the final state to extract results
        final_state = await master_content_graph.aget_state(config)
        state_values = final_state.values

        generated_content = state_values.get("generated_content")
        feedback = state_values.get("feedback", "")

        if generated_content and not generated_content.get("_parse_error"):
            # Extract the record id from the last message
            messages = state_values.get("messages", [])
            record_id = None
            for msg in reversed(messages):
                content = msg.content if hasattr(msg, "content") else str(msg)
                if "Record ID:" in content:
                    record_id = content.split("Record ID:")[-1].strip()
                    break

            yield sse_event(
                "done",
                masterContent=generated_content,
                masterContentId=record_id,
                feedback=feedback,
            )
        else:
            yield sse_event(
                "error",
                error=feedback or "Failed to generate master content.",
                step="Agent execution",
            )

    except Exception as e:
        logger.error(f"Error in master content event generator: {e}")
        yield sse_event("error", error=str(e), step="Unexpected error")
