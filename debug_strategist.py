import asyncio
from langchain_core.messages import HumanMessage
from marketing_team.nodes import strategist_node
from marketing_team.state import MarketingState

async def debug_strategist():
    print("Debugging Strategist Node...")
    state = {
        "messages": [
            HumanMessage(content="I want to start a premium coffee shop in Hanoi called 'Black Gold'.")
        ],
        "next": "Strategist"
    }
    
    print("Invoking strategist_node...")
    try:
        result = await strategist_node(state, {})
        print("Strategist Result:", result)
    except Exception as e:
        print(f"Error in strategist_node: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_strategist())
