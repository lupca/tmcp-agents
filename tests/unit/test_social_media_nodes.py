import sys
from unittest.mock import MagicMock

# --- Mocking dependencies before import ---
# We need to mock langchain_core, langchain_ollama, and langgraph

mock_langchain_core = MagicMock()
sys.modules["langchain_core"] = mock_langchain_core
sys.modules["langchain_core.messages"] = mock_langchain_core.messages
sys.modules["langchain_core.prompts"] = mock_langchain_core.prompts
sys.modules["langchain_core.runnables"] = mock_langchain_core.runnables

mock_langchain_ollama = MagicMock()
sys.modules["langchain_ollama"] = mock_langchain_ollama

mock_langgraph = MagicMock()
sys.modules["langgraph"] = mock_langgraph
sys.modules["langgraph.graph"] = mock_langgraph.graph
sys.modules["langgraph.graph.message"] = mock_langgraph.graph.message

# Define mock message classes
class MockMessage:
    def __init__(self, content, name=None, **kwargs):
        self.content = content
        self.name = name

    def __eq__(self, other):
        return self.content == other.content and self.name == other.name

class HumanMessage(MockMessage): pass
class AIMessage(MockMessage): pass
class SystemMessage(MockMessage): pass

mock_langchain_core.messages.HumanMessage = HumanMessage
mock_langchain_core.messages.AIMessage = AIMessage
mock_langchain_core.messages.SystemMessage = SystemMessage

# Import nodes AFTER mocking
import pytest
from unittest.mock import patch, AsyncMock
from social_media_poster.state import SocialMediaState
from social_media_poster.nodes import (
    content_retriever_node,
    post_generator_node,
    evaluator_node
)

@pytest.fixture
def mock_social_media_state():
    return SocialMediaState(
        messages=[],
        context_data={},
        generated_post=None,
        next_node=None,
        feedback=None
    )

def test_content_retriever_node(mock_social_media_state):
    with patch("social_media_poster.nodes.fetch_branch_data") as mock_fetch_branch, \
         patch("social_media_poster.nodes.fetch_worksheet") as mock_fetch_worksheet, \
         patch("social_media_poster.nodes.fetch_customer_profile") as mock_fetch_customer, \
         patch("social_media_poster.nodes.fetch_brand_identity") as mock_fetch_brand, \
         patch("social_media_poster.nodes.fetch_campaign") as mock_fetch_campaign, \
         patch("social_media_poster.nodes.fetch_event") as mock_fetch_event, \
         patch("social_media_poster.nodes.search_web") as mock_search_web, \
         patch("social_media_poster.nodes.rag_search") as mock_rag_search:

        mock_fetch_branch.return_value = {"branch": "test"}
        mock_fetch_worksheet.return_value = {"worksheet": "test"}
        mock_fetch_customer.return_value = {"customer": "test"}
        mock_fetch_brand.return_value = {"brand": "test"}
        mock_fetch_campaign.return_value = {"campaign": "test"}
        mock_fetch_event.return_value = {"event": "test"}
        mock_search_web.return_value = [{"title": "test", "url": "http://test.com"}]
        mock_rag_search.return_value = "rag context"

        result = content_retriever_node(mock_social_media_state)

        assert "context_data" in result
        context = result["context_data"]
        assert context["branch"] == {"branch": "test"}
        assert context["rag_context"] == "rag context"

def test_post_generator_node(mock_social_media_state):
    mock_social_media_state["context_data"] = {
        "worksheet": {"language": "English"},
        "brandIdentity": {"brandName": "TestBrand"},
    }

    # Mock llm.invoke
    mock_response = AIMessage(content="Generated Post Content")

    with patch("social_media_poster.nodes.llm") as mock_llm:
        mock_llm.invoke.return_value = mock_response

        result = post_generator_node(mock_social_media_state)

        assert "generated_post" in result
        assert result["generated_post"] == "Generated Post Content"

def test_evaluator_node_context_check(mock_social_media_state):
    # Test checking context (no post generated yet)
    mock_social_media_state["generated_post"] = None
    mock_social_media_state["context_data"] = {} # Empty context

    result = evaluator_node(mock_social_media_state)
    assert result["next_node"] == "Retriever"
    assert "feedback" in result

    # Test good context
    mock_social_media_state["context_data"] = {
        "worksheet": {"exists": True},
        "campaign": {"exists": True}
    }
    result = evaluator_node(mock_social_media_state)
    assert result["next_node"] == "PostGenerator"


def test_evaluator_node_post_check(mock_social_media_state):
    mock_social_media_state["generated_post"] = "Some post"

    with patch("social_media_poster.nodes.llm") as mock_llm:
        # Test Approved
        mock_llm.invoke.return_value = AIMessage(content="APPROVED")
        result = evaluator_node(mock_social_media_state)
        assert result["next_node"] == "FINISH"

        # Test Rejected
        mock_llm.invoke.return_value = AIMessage(content="RETRY: Too boring")
        result = evaluator_node(mock_social_media_state)
        assert result["next_node"] == "PostGenerator"
