import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage

from agent import app_graph
from app.utils.sse import sse_event

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def chat_event_generator(message: str, thread_id: str) -> AsyncGenerator[str, None]:
    """
    Generates Server-Sent Events (SSE) from the LangGraph execution.
    """
    inputs = {"messages": [HumanMessage(content=message)]}
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Use astream_events to catch detailed execution steps
        async for event in app_graph.astream_events(inputs, config=config, version="v2"):
            event_type = event["event"]

            # 1. Agent Thinking / Starting LLM
            if event_type == "on_chat_model_start":
                metadata = event.get("metadata", {})
                yield sse_event("status", status="thinking", agent=metadata.get("langgraph_node", "Agent"))

            # 2. Tool Execution Start
            elif event_type == "on_tool_start":
                yield sse_event("tool_start", tool=event["name"], input=event["data"].get("input"))

            # 3. Tool Execution End
            elif event_type == "on_tool_end":
                output = event["data"].get("output")
                yield sse_event("tool_end", tool=event["name"], output=str(output))

            # 4. Agent Streaming Tokens
            elif event_type == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield sse_event("chunk", content=chunk.content)

            # 5. Node Transitions
            elif event_type == "on_chain_start":
                name = event["name"]
                if name in ["Strategist", "Researcher", "CampaignManager", "ContentCreator", "Supervisor"]:
                    yield sse_event("status", status="active", agent=name)

        # Final message when done
        yield sse_event("done")

    except Exception as e:
        logger.error(f"Error in event generator: {e}")
        yield sse_event("error", error=str(e))
