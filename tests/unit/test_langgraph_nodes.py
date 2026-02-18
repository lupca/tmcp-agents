
import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from marketing_team.state import MarketingState
from marketing_team.nodes import (
    run_node_agent,
    supervisor_node,
    strategist_node
)

# --- Test run_node_agent ---

@pytest.mark.asyncio
async def test_run_node_agent_simple_response():
    # Mock state
    state = MarketingState(messages=[HumanMessage(content="Hello")], next="")
    config = RunnableConfig(configurable={"thread_id": "1"})
    
    # Mock LLM behavior
    mock_llm_response = AIMessage(content="Hello there!")
    
    # We need to mock the llm object in nodes.py
    with patch("marketing_team.nodes.llm") as mock_llm:
        # bind_tools returns a runnable
        mock_bound_llm = AsyncMock()
        mock_bound_llm.ainvoke.return_value = mock_llm_response
        mock_llm.bind_tools.return_value = mock_bound_llm
        
        result = await run_node_agent(state, "System Prompt", "TestAgent", config)
        
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], HumanMessage)
        assert result["messages"][0].content == "Hello there!"
        assert result["messages"][0].name == "TestAgent"

@pytest.mark.asyncio
async def test_run_node_agent_with_tool_call():
    # This is a bit more complex. 
    # 1. LLM mocks returning a tool call
    # 2. ToolNode mocks executing the tool
    # 3. LLM mocks returning final answer after tool output
    
    state = MarketingState(messages=[HumanMessage(content="Do something")], next="")
    config = RunnableConfig(configurable={"thread_id": "1"})
    
    # Mock generic tool call
    tool_call_id = "call_123"
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{"name": "test_tool", "args": {"arg": "val"}, "id": tool_call_id}]
    )
    final_response_msg = AIMessage(content="Done.")
    
    # Mock Tool execution result
    tool_output_msg = HumanMessage(content="Tool Result", name="test_tool", tool_call_id=tool_call_id)
    
    with patch("marketing_team.nodes.llm") as mock_llm, \
         patch("marketing_team.nodes.ToolNode") as MockToolNode:
        
        # Setup LLM chain
        mock_bound_llm = AsyncMock()
        # Side effect to return tool call first, then final response
        mock_bound_llm.ainvoke.side_effect = [tool_call_msg, final_response_msg]
        mock_llm.bind_tools.return_value = mock_bound_llm
        
        # Setup ToolNode
        mock_tool_executor = AsyncMock()
        mock_tool_executor.ainvoke.return_value = {"messages": [tool_output_msg]}
        MockToolNode.return_value = mock_tool_executor
        
        result = await run_node_agent(state, "System Prompt", "TestAgent", config)
        
        # Assertions
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "Done."
        
        # Verify LLM was called twice
        assert mock_bound_llm.ainvoke.call_count == 2
        
        # Verify Tool was executed
        mock_tool_executor.ainvoke.assert_called_once()


# --- Test supervisor_node ---

@pytest.mark.asyncio
async def test_supervisor_node_routing():
    # Test routing to Strategist
    state = MarketingState(messages=[], next="")
    
    # supervisor_chain.ainvoke(state) returns a message with agent name
    with patch("marketing_team.nodes.supervisor_chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(return_value=AIMessage(content="Strategist"))
        
        result = await supervisor_node(state)
        assert result["next"] == "Strategist"
        
    # Test routing to FINISH
    with patch("marketing_team.nodes.supervisor_chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(return_value=AIMessage(content="FINISH"))
        
        result = await supervisor_node(state)
        assert "FINISH" in result["next"] or result["next"] == "FINISH"

# --- Test specific node (Strategist) ---
# Just verifying it calls run_node_agent with correct prompt

@pytest.mark.asyncio
async def test_strategist_node_calls_run_agent():
    state = MarketingState(messages=[], next="")
    config = RunnableConfig(configurable={"thread_id": "1"})
    
    with patch("marketing_team.nodes.run_node_agent") as mock_run_agent:
        mock_run_agent.return_value = {"messages": []}
        
        await strategist_node(state, config)
        
        mock_run_agent.assert_called_once()
        args, kwargs = mock_run_agent.call_args
        assert args[1] is not None # Prompt should be passed
        assert args[2] == "Strategist"
