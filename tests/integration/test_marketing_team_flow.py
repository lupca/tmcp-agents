import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from langchain_core.messages import HumanMessage
from marketing_team.graph import marketing_graph


async def run_marketing_team():
    # Example business idea
    user_request = """
    I have a business idea: 'EcoWare' - sustainable, edible cutlery made from rice flour.
    Target audience: environmentally conscious millennials and event organizers.
    I need a full marketing strategy and 3 launch posts for Instagram.
    """
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"Starting Marketing Team with Thread ID: {thread_id}")
    print("-" * 50)
    
    inputs = {
        "messages": [HumanMessage(content=user_request)]
    }
    
    # Run the graph
    async for event in marketing_graph.astream(inputs, config=config):
        for key, value in event.items():
            print(f"\n--- Node: {key} ---")
            if "messages" in value:
                last_msg = value["messages"][-1]
                print(f"{last_msg.name}: {last_msg.content[:200]}...") # Print first 200 chars
            elif "next" in value:
                print(f"Supervisor routed to: {value['next']}")
            else:
                print(value)
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(run_marketing_team())
