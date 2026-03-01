import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import asyncio
import uuid
from agent import app_graph
from langchain_core.messages import HumanMessage

async def test_integration():
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"Starting conversation with thread_id: {thread_id}")
    
    print("\n-- Turn 1: 'List all collections' --")
    inputs = {"messages": [HumanMessage(content="List all collections available in PocketBase.")]}
    
    try:
        # Initial response might be a tool call
        result = await app_graph.ainvoke(inputs, config=config)
        
        last_msg = result["messages"][-1]
        print("Final Output:", last_msg.content)
        
        # If the agent called a tool, we should see it in the messages
        for m in result["messages"]:
            if hasattr(m, "tool_calls") and m.tool_calls:
                print("Tool called:", m.tool_calls)
            if hasattr(m, "tool_call_id"): # ToolMessage
                 print("Tool Output:", m.content)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_integration())
