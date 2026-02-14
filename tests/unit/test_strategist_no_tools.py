import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import asyncio
from langchain_core.messages import HumanMessage

from langgraph.prebuilt import create_react_agent
# from mcp_bridge import all_tools # Commented out

# Mock tools as empty list
all_tools = []

STRATEGIST_PROMPT = "You are a strategist."

from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)

async def test_strategist_no_tools():
    print("Debugging Strategist Node (No Tools)...")
    
    agent = create_react_agent(llm, tools=all_tools, prompt=STRATEGIST_PROMPT)
    
    state = {
        "messages": [
            HumanMessage(content="I want to start a premium coffee shop in Hanoi called 'Black Gold'.")
        ]
    }
    
    print("Invoking agent...")
    try:
        result = await agent.ainvoke(state, {})
        print("Strategist Result:", result)
    except Exception as e:
        print(f"Error in strategist_node: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_strategist_no_tools())
