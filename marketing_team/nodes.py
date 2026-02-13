from typing import Literal
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from mcp_bridge import all_tools
from .state import MarketingState
from .prompts import (
    STRATEGIST_PROMPT,
    CAMPAIGN_MANAGER_PROMPT,
    RESEARCHER_PROMPT,
    CONTENT_CREATOR_PROMPT,
    SUPERVISOR_PROMPT
)

# --- LLM Configuration ---
# Using the same configuration as the main agent
from langchain_ollama import ChatOllama
llm = ChatOllama(model="qwen2.5", temperature=0, base_url="http://172.20.10.8:11434")

# --- Agent Nodes ---


# --- Helper for Manual Tool Loop ---
from langgraph.prebuilt import ToolNode
from langchain_core.messages import ToolMessage
from langchain_community.tools import DuckDuckGoSearchRun

# Define the search tool
search_tool = DuckDuckGoSearchRun()

async def run_node_agent(state: MarketingState, prompt: str, name: str, config: RunnableConfig, tools=all_tools):
    """
    Runs an agent node with manual tool execution loop.
    Allows specifying custom tools for different agents.
    """
    # 1. Bind tools to the LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # Create a ToolNode for this specific set of tools
    tool_executor = ToolNode(tools)
    
    # 2. Add system prompt to messages
    messages = [SystemMessage(content=prompt)] + state["messages"]
    
    # 3. Validation / Loop limit
    max_steps = 10
    step = 0
    
    while step < max_steps:
        # 4. Invoke LLM
        # IMPORTANT: Use ainvoke
        result = await llm_with_tools.ainvoke(messages, config)
        messages.append(result)
        
        # 5. Check for tool calls
        if not result.tool_calls:
            # Final response
            return {
                "messages": [
                    HumanMessage(content=result.content, name=name)
                ]
            }
        
        # 6. Execute tools
        # ToolNode expects a dict with "messages" (last message having tool_calls)
        # It returns a dict with "messages" (ToolMessages)
        tool_output = await tool_executor.ainvoke({"messages": [result]}, config)
        
        # 7. Append tool outputs to history
        for tool_msg in tool_output["messages"]:
            messages.append(tool_msg)
            
        step += 1
    
    return {
        "messages": [
            HumanMessage(content="Agent reached max steps without final answer.", name=name)
        ]
    }

# --- Agent Nodes ---

async def strategist_node(state: MarketingState, config: RunnableConfig):
    return await run_node_agent(state, STRATEGIST_PROMPT, "Strategist", config)

async def campaign_manager_node(state: MarketingState, config: RunnableConfig):
    return await run_node_agent(state, CAMPAIGN_MANAGER_PROMPT, "CampaignManager", config)

async def researcher_node(state: MarketingState, config: RunnableConfig):
    # Only Researcher gets the search tool
    researcher_tools = all_tools + [search_tool]
    return await run_node_agent(state, RESEARCHER_PROMPT, "Researcher", config, tools=researcher_tools)

async def content_creator_node(state: MarketingState, config: RunnableConfig):
    return await run_node_agent(state, CONTENT_CREATOR_PROMPT, "ContentCreator", config)

# --- Supervisor Node ---
# The Supervisor decides which agent to call next.

members = ["Strategist", "CampaignManager", "Researcher", "ContentCreator"]
system_prompt = SUPERVISOR_PROMPT.format(members=members)
options = ", ".join(members)

# Ensure options are properly formatted in the prompt string
next_step_prompt = f"Given the conversation above, who should act next? Select one of: {options} or FINISH."

supervisor_chain = (
    ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("placeholder", "{messages}"),
            (
                "system",
                next_step_prompt
            ),
        ]
    )
    | llm
)

def supervisor_node(state: MarketingState):
    result = supervisor_chain.invoke(state)
    next_agent = result.content.strip()
    
    # Simple parsing to clearer logic
    if "Strategist" in next_agent:
        return {"next": "Strategist"}
    elif "CampaignManager" in next_agent:
        return {"next": "CampaignManager"}
    elif "Researcher" in next_agent:
        return {"next": "Researcher"}
    elif "ContentCreator" in next_agent:
        return {"next": "ContentCreator"}
    else:
        return {"next": "FINISH"}
