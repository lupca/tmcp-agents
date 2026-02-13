
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import chainlit as cl

from agent import app_graph
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END

import uuid

@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("graph", app_graph)
    # Generate a unique thread ID for this session to maintain conversation history
    thread_id = str(uuid.uuid4())
    cl.user_session.set("thread_id", thread_id)
    await cl.Message(content="Hello! I'm your blog post assistant. I can help you write and publish posts to PocketBase.").send()

@cl.on_message
async def on_message(message: cl.Message):
    graph = cl.user_session.get("graph")
    thread_id = cl.user_session.get("thread_id")
    
    # Run the graph with the session's thread ID
    config = {"configurable": {"thread_id": thread_id}}
    inputs = {"messages": [HumanMessage(content=message.content)]}
    
    # Stream the results
    msg = cl.Message(content="")
    
    async for event in graph.astream_events(inputs, config=config, version="v1"):
        kind = event["event"]
        
        if kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                await msg.stream_token(content)
                
    await msg.send()
