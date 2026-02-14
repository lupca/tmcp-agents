import json
import logging
from typing import AsyncGenerator
from langchain_core.messages import HumanMessage
from agent import app_graph

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
        # version="v1" is required for astream_events
        async for event in app_graph.astream_events(inputs, config=config, version="v2"):
            event_type = event["event"]
            
            # 1. Agent Thinking / Starting LLM
            if event_type == "on_chat_model_start":
                # Check if it's the main agent model (not some internal helper)
                metadata = event.get("metadata", {})
                yield f"data: {json.dumps({'type': 'status', 'status': 'thinking', 'agent': metadata.get('langgraph_node', 'Agent')})}\n\n"

            # 2. Tool Execution Start
            elif event_type == "on_tool_start":
                tool_name = event["name"]
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name, 'input': event['data'].get('input')})}\n\n"

            # 3. Tool Execution End
            elif event_type == "on_tool_end":
                tool_name = event["name"]
                # output can be diverse, ensure it's serializable
                output = event["data"].get("output")
                yield f"data: {json.dumps({'type': 'tool_end', 'tool': tool_name, 'output': str(output)})}\n\n"
            
            # 4. Agent Streaming Tokens (Optional - for real-time text)
            elif event_type == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk.content})}\n\n"

            # 5. Node Transitions
            elif event_type == "on_chain_start":
                 # Filter for graph nodes to show "Agent switching" or similar if needed
                 name = event["name"]
                 # Avoid showing every single chain start, focus on high-level nodes if possible
                 if name in ["Strategist", "Researcher", "CampaignManager", "ContentCreator", "Supervisor"]:
                     yield f"data: {json.dumps({'type': 'status', 'status': 'active', 'agent': name})}\n\n"

        # Final message when done
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        logger.error(f"Error in event generator: {e}")
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
