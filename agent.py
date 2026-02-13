import os
import requests
from typing import Annotated, TypedDict, Literal

from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# --- Configuration ---
POCKETBASE_URL = os.getenv("POCKETBASE_URL", "http://127.0.0.1:8090")
POCKETBASE_USER = os.getenv("POCKETBASE_USER", "admin@admin.com")
POCKETBASE_PASSWORD = os.getenv("POCKETBASE_PASSWORD", "123qweasdzxc")
MODEL_NAME = "qwen2.5"

# --- Tools ---

@tool
def ingest_post(title: str, slug: str, content: str, summary: str) -> str:
    """
    Creates a new blog post in PocketBase.
    
    Args:
        title: The title of the post.
        slug: The URL slug for the post.
        content: The main content of the post (can be HTML or Markdown).
        summary: A short summary of the post.
        
    Returns:
        A JSON string containing the response from PocketBase, or an error message.
    """
    try:
        # 1. Authenticate
        auth_url = f"{POCKETBASE_URL}/api/collections/users/auth-with-password"
        auth_data = {
            "identity": POCKETBASE_USER,
            "password": POCKETBASE_PASSWORD
        }
        auth_res = requests.post(auth_url, json=auth_data)
        auth_res.raise_for_status()
        token = auth_res.json()["token"]

        # 2. Create Post
        create_url = f"{POCKETBASE_URL}/api/collections/posts/records"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        post_payload = {
            "title": title,
            "slug": slug,
            "content": content,
            "summary": summary,
            "status": "draft" 
        }
        
        response = requests.post(create_url, json=post_payload, headers=headers)
        response.raise_for_status()
        
        return str(response.json())
        
    except requests.exceptions.RequestException as e:
        return f"Error communicating with PocketBase: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

# --- Agent Components ---

# Define the state
class State(TypedDict):
    messages: Annotated[list, add_messages]

# Initialize the LLM
llm = ChatOllama(model=MODEL_NAME, temperature=0.7)

# Bind tools to the LLM
tools = [ingest_post]
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
