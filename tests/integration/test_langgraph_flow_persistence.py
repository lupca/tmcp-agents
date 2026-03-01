
import pytest
from unittest.mock import patch
from langchain_core.messages import HumanMessage, AIMessage
from marketing_team.graph import marketing_graph

@pytest.mark.asyncio
async def test_conditional_edges_routing():
    """
    Test that the graph routes to the correct node based on Supervisor's decision.
    We mock the supervisor_chain to return specific agents.
    """
    # We patch the supervisor_chain used in nodes.py
    # and run_node_agent to avoid actual LLM calls in worker nodes
    
    with patch("marketing_team.nodes.supervisor_chain") as mock_supervisor, \
         patch("marketing_team.nodes.run_node_agent") as mock_run_agent:
             
        # Scenario: Supervisor routes to Strategist, then FINISH
        # invocation 1: Supervisor -> returns "Strategist"
        # invocation 2: Strategist runs (mocked)
        # invocation 3: Supervisor -> returns "FINISH"
        
        # side_effect for supervisor chain invoke
        mock_supervisor.invoke.side_effect = [
            AIMessage(content="Strategist"),
            AIMessage(content="FINISH")
        ]
        
        # mock worker node response
        mock_run_agent.return_value = {
            "messages": [HumanMessage(content="Strategist Work Done", name="Strategist")]
        }
        
        # Run graph
        chain = marketing_graph
        inputs = {"messages": [HumanMessage(content="Start project")]}
        config = {"configurable": {"thread_id": "test_routing_1"}}
        
        # We collect outputs to see the path
        events = []
        async for event in chain.astream(inputs, config=config):
            events.append(event)
            
        # Analyze events
        # We expect:
        # 1. Supervisor output: {"Supervisor": {"next": "Strategist"}}
        # 2. Strategist output: {"Strategist": {"messages": [...]}}
        # 3. Supervisor output: {"Supervisor": {"next": "FINISH"}}
        
        node_names = []
        for e in events:
            node_names.extend(e.keys())
            
        assert "Supervisor" in node_names
        assert "Strategist" in node_names
        
        # Verify Strategist was called
        assert mock_run_agent.called
        assert mock_run_agent.call_count >= 1

@pytest.mark.asyncio
async def test_state_persistence():
    """
    Test that the graph persists state across different runs with the same thread_id.
    """
    thread_id = "test_persistence_1"
    config = {"configurable": {"thread_id": thread_id}}
    
    with patch("marketing_team.nodes.supervisor_chain") as mock_supervisor, \
         patch("marketing_team.nodes.run_node_agent") as mock_run_agent:
             
        # Run 1: Supervisor -> Strategist -> Supervisor -> FINISH (to stop execution for this run)
        mock_supervisor.invoke.side_effect = [
            AIMessage(content="Strategist"),
            AIMessage(content="FINISH") # Stop the first run
        ]
        mock_run_agent.return_value = {
            "messages": [HumanMessage(content="Strategist Output 1", name="Strategist")]
        }
        
        inputs_1 = {"messages": [HumanMessage(content="Run 1")]}
        await marketing_graph.ainvoke(inputs_1, config=config)
        
        # Get current state
        snapshot_1 = marketing_graph.get_state(config)
        messages_1 = snapshot_1.values["messages"]
        # Should contain: User "Run 1", Strategist "Strategist Output 1"
        assert any(m.content == "Run 1" for m in messages_1)
        assert any(m.content == "Strategist Output 1" for m in messages_1)
        
        # Run 2: Continue conversation. Supervisor -> CampaignManager -> FINISH
        # Note: We need to reset side_effect or just append to it if possible, 
        # but since we re-enter context context, we set it up again for new call? 
        # Actually within the same 'with' block, we can just continue using the mock.
        
        # CAUTION: The 'side_effect' iterator might be exhausted if we reused the same mock object 
        # without resetting or providing enough values.
        # Let's reset side_effect for the next run or provide enough values initially.
        # But wait, 'ainvoke' creates a new loop? No, side_effect is on the mock object which persists in the block.
        
        mock_supervisor.invoke.side_effect = [
            AIMessage(content="CampaignManager"),
            AIMessage(content="FINISH")
        ]
        
        mock_run_agent.return_value = {
            "messages": [HumanMessage(content="CampaignManager Output 2", name="CampaignManager")]
        }
        
        inputs_2 = {"messages": [HumanMessage(content="Run 2")]}
        await marketing_graph.ainvoke(inputs_2, config=config)
        
        # Get state again
        snapshot_2 = marketing_graph.get_state(config)
        messages_2 = snapshot_2.values["messages"]
        
        # Should contain ALL messages
        content_list = [m.content for m in messages_2]
        assert "Run 1" in content_list
        assert "Strategist Output 1" in content_list
        assert "Run 2" in content_list
        assert "CampaignManager Output 2" in content_list
