import sys
from unittest.mock import MagicMock

# --- Mocking dependencies ---
# We need to mock langgraph, langchain_core, and langchain_ollama
# Note: In a real environment with dependencies installed, these mocks wouldn't be necessary
# or would be handled differently.

mock_langgraph = MagicMock()
sys.modules["langgraph"] = mock_langgraph
sys.modules["langgraph.graph"] = mock_langgraph.graph
sys.modules["langgraph.graph.message"] = mock_langgraph.graph.message
sys.modules["langgraph.checkpoint"] = mock_langgraph.checkpoint
sys.modules["langgraph.checkpoint.memory"] = mock_langgraph.checkpoint.memory

# Mock StateGraph class
mock_state_graph_class = MagicMock()
mock_langgraph.graph.StateGraph = mock_state_graph_class
mock_langgraph.graph.START = "START"
mock_langgraph.graph.END = "END"

# Mock MemorySaver
mock_memory_saver_class = MagicMock()
mock_langgraph.checkpoint.memory.MemorySaver = mock_memory_saver_class

# Mock langchain_core and ollama (needed by nodes.py)
mock_langchain_core = MagicMock()
sys.modules["langchain_core"] = mock_langchain_core
sys.modules["langchain_core.messages"] = mock_langchain_core.messages
sys.modules["langchain_core.prompts"] = mock_langchain_core.prompts
sys.modules["langchain_core.runnables"] = mock_langchain_core.runnables

mock_langchain_ollama = MagicMock()
sys.modules["langchain_ollama"] = mock_langchain_ollama

# Mock Message classes
class MockMessage:
    def __init__(self, content, name=None, **kwargs):
        self.content = content
        self.name = name

class HumanMessage(MockMessage): pass
class AIMessage(MockMessage): pass
class SystemMessage(MockMessage): pass

mock_langchain_core.messages.HumanMessage = HumanMessage
mock_langchain_core.messages.AIMessage = AIMessage
mock_langchain_core.messages.SystemMessage = SystemMessage


import pytest
# Now import graph
from social_media_poster.graph import workflow
from social_media_poster.nodes import content_retriever_node, post_generator_node, evaluator_node

def test_social_media_graph_structure():
    # workflow is the mock instance returned by StateGraph(...)
    # Because StateGraph is mocked, workflow should be a MagicMock

    # Check if add_node was called correctly
    workflow.add_node.assert_any_call("Retriever", content_retriever_node)
    workflow.add_node.assert_any_call("PostGenerator", post_generator_node)
    workflow.add_node.assert_any_call("Evaluator", evaluator_node)

    # Check edges
    workflow.add_edge.assert_any_call("START", "Retriever")
    workflow.add_edge.assert_any_call("Retriever", "Evaluator")
    workflow.add_edge.assert_any_call("PostGenerator", "Evaluator")

    # Check conditional edges
    # We retrieve the arguments passed to the last call (or we can iterate)
    # Since we only have one add_conditional_edges call in graph.py
    args, _ = workflow.add_conditional_edges.call_args

    assert args[0] == "Evaluator"
    # args[1] is the function determine_next_node
    assert args[2] == {
        "Retriever": "Retriever",
        "PostGenerator": "PostGenerator",
        "END": "END"
    }

    # Check compile
    workflow.compile.assert_called()
