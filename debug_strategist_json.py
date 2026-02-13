import asyncio
from typing import Any, Dict
from langchain_core.messages import HumanMessage, SystemMessage

from mcp_bridge import create_record

# Only create_record tool
tools = [create_record]

STRATEGIST_PROMPT = "You are a strategist. Create a record in 'business_ideas' with data_json '{\"foo\": \"bar\"}'."

from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)

async def debug_strategist_json():
    print("Debugging Strategist Node (create_record JSON)...")
    
    llm_with_tools = llm.bind_tools(tools)
    messages = [
        SystemMessage(content=STRATEGIST_PROMPT),
        HumanMessage(content="Go.")
    ]
    
    print("Invoking llm...")
    try:
        # Using ainvoke
        result = await llm_with_tools.ainvoke(messages)
        print("Result:", result)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_strategist_json())
