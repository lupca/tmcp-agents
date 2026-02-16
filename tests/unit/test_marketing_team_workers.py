import sys
from unittest.mock import MagicMock

# --- Mocking dependencies ---
mock_langchain_core = MagicMock()
sys.modules["langchain_core"] = mock_langchain_core
sys.modules["langchain_core.messages"] = mock_langchain_core.messages
sys.modules["langchain_core.prompts"] = mock_langchain_core.prompts
sys.modules["langchain_core.runnables"] = mock_langchain_core.runnables

mock_langchain_community = MagicMock()
sys.modules["langchain_community"] = mock_langchain_community
sys.modules["langchain_community.tools"] = mock_langchain_community.tools

mock_langgraph = MagicMock()
sys.modules["langgraph"] = mock_langgraph
sys.modules["langgraph.graph"] = mock_langgraph.graph
sys.modules["langgraph.graph.message"] = mock_langgraph.graph.message
sys.modules["langgraph.prebuilt"] = mock_langgraph.prebuilt

# Mock app.core and app.tools
mock_app = MagicMock()
sys.modules["app"] = mock_app
sys.modules["app.core"] = mock_app.core
sys.modules["app.core.llm_factory"] = mock_app.core.llm_factory
sys.modules["app.tools"] = mock_app.tools
sys.modules["app.tools.mcp_bridge"] = mock_app.tools.mcp_bridge

# Define mock message classes
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

# RunnableConfig mock
class RunnableConfig(dict):
    pass
mock_langchain_core.runnables.RunnableConfig = RunnableConfig


import pytest
import asyncio
from unittest.mock import patch, AsyncMock

# Import nodes AFTER mocking
from marketing_team.state import MarketingState
from marketing_team.nodes import (
    campaign_manager_node,
    researcher_node,
    content_creator_node,
    CAMPAIGN_MANAGER_PROMPT,
    RESEARCHER_PROMPT,
    CONTENT_CREATOR_PROMPT
)

@pytest.fixture
def mock_state():
    return MarketingState(messages=[], next="")

@pytest.fixture
def mock_config():
    return RunnableConfig(configurable={"thread_id": "1"})

def test_campaign_manager_node(mock_state, mock_config):
    async def _test():
        with patch("marketing_team.nodes.run_node_agent") as mock_run_agent:
            mock_run_agent.return_value = {"messages": []}

            await campaign_manager_node(mock_state, mock_config)

            mock_run_agent.assert_called_once()
            args, kwargs = mock_run_agent.call_args
            # args: state, prompt, name, config, tools (optional)
            assert args[1] == CAMPAIGN_MANAGER_PROMPT
            assert args[2] == "CampaignManager"
    asyncio.run(_test())

def test_researcher_node(mock_state, mock_config):
    async def _test():
        with patch("marketing_team.nodes.run_node_agent") as mock_run_agent:
            mock_run_agent.return_value = {"messages": []}

            await researcher_node(mock_state, mock_config)

            mock_run_agent.assert_called_once()
            args, kwargs = mock_run_agent.call_args
            assert args[1] == RESEARCHER_PROMPT
            assert args[2] == "Researcher"
            # Check if tools are passed (researcher has extra tools)
            # run_node_agent signature: (state, prompt, name, config, tools=all_tools)
            # So tools is likely in kwargs or 5th arg
            if "tools" in kwargs:
                assert kwargs["tools"] is not None
            elif len(args) > 4:
                assert args[4] is not None
    asyncio.run(_test())

def test_content_creator_node(mock_state, mock_config):
    async def _test():
        with patch("marketing_team.nodes.run_node_agent") as mock_run_agent:
            mock_run_agent.return_value = {"messages": []}

            await content_creator_node(mock_state, mock_config)

            mock_run_agent.assert_called_once()
            args, kwargs = mock_run_agent.call_args
            assert args[1] == CONTENT_CREATOR_PROMPT
            assert args[2] == "ContentCreator"
    asyncio.run(_test())
