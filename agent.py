import os
from typing import Annotated, TypedDict, Literal

from langchain_core.tools import tool

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from mcp_bridge import all_tools

# --- Configuration ---
MODEL_NAME = "gemini-2.5-flash"

# --- Tools ---
# Tools are now imported from mcp_bridge.py

# --- Agent Components ---

# Define the state
class State(TypedDict):
    messages: Annotated[list, add_messages]

# Initialize the LLM
from langchain_google_genai import ChatGoogleGenerativeAI

# Initialize the LLM
# Ensure GOOGLE_API_KEY is set in your environment
llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=0)

# Bind tools to the LLM
tools = all_tools
llm_with_tools = llm.bind_tools(tools)

# Define nodes
def chatbot(state: State):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

# Build the graph
graph_builder = StateGraph(State)

graph_builder.add_node("chatbot", chatbot)
tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)

graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,
)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge("chatbot", END)

from langgraph.checkpoint.memory import MemorySaver



memory = MemorySaver()
app_graph = graph_builder.compile(checkpointer=memory)
