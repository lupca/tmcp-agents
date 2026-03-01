import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import asyncio
from langchain_core.messages import HumanMessage, SystemMessage

from app.tools.mcp_bridge import list_collections

# Only one tool
tools = [list_collections]

STRATEGIST_PROMPT = "You are a strategist. List the collections in the database."

from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)

async def test_strategist_one_tool():
    print("Debugging Strategist Node (One Tool)...")
    
    llm_with_tools = llm.bind_tools(tools)
    messages = [
        SystemMessage(content=STRATEGIST_PROMPT),
        HumanMessage(content="Go.")
    ]
    
    print("Invoking llm...")
    try:
        result = await llm_with_tools.ainvoke(messages)
        print("Result:", result)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_strategist_one_tool())
