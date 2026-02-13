from agent import app_graph
from langchain_core.messages import HumanMessage
import uuid

def test_agent():
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"Starting conversation with thread_id: {thread_id}")
    
    # Turn 1
    print("\n-- Turn 1: 'My name is Bob' --")
    inputs = {"messages": [HumanMessage(content="My name is Bob.")]}
    result = app_graph.invoke(inputs, config=config)
    print("Agent output:", result["messages"][-1].content)
    
    # Turn 2
    print("\n-- Turn 2: 'What is my name?' --")
    inputs = {"messages": [HumanMessage(content="What is my name?")]}
    result = app_graph.invoke(inputs, config=config)
    print("Agent output:", result["messages"][-1].content)

if __name__ == "__main__":
    test_agent()
