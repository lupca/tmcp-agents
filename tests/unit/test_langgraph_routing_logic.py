
from unittest.mock import patch
from langchain_core.messages import HumanMessage, AIMessage
from marketing_team.state import MarketingState
from marketing_team.nodes import supervisor_node

# --- Testing the Routing Logic (Supervisor) ---

def test_supervisor_routing_continue_to_agent():
    """
    Test routing logic: When LLM decides on an agent, 
    the router (supervisor_node) should update state["next"] to that agent.
    This corresponds to 'should_continue' -> 'continue' (to next node).
    """
    # 1. Mock State
    state = MarketingState(messages=[
        HumanMessage(content="I need a marketing strategy for my new coffee brand.")
    ], next="")

    # 2. Mock Supervisor LLM Chain
    with patch("marketing_team.nodes.supervisor_chain") as mock_chain:
        # Simulate LLM choosing 'Strategist'
        mock_chain.invoke.return_value = AIMessage(content="Strategist")
        
        # 3. Execute Node
        result = supervisor_node(state)
        
        # 4. Assert Routing Decision
        assert result["next"] == "Strategist"
        # In the graph, this will trigger the conditional edge to 'Strategist'

def test_supervisor_routing_finish():
    """
    Test routing logic: When LLM decides to FINISH,
    the router should update state["next"] to FINISH (or END).
    This corresponds to 'should_continue' -> 'end'.
    """
    # 1. Mock State (Conversation ending)
    state = MarketingState(messages=[
        HumanMessage(content="I need a strategy."),
        AIMessage(content="Here is your strategy.", name="Strategist"),
        HumanMessage(content="looks good, thanks!")
    ], next="")

    # 2. Mock Supervisor LLM Chain
    with patch("marketing_team.nodes.supervisor_chain") as mock_chain:
        # Simulate LLM choosing 'FINISH'
        mock_chain.invoke.return_value = AIMessage(content="FINISH")
        
        # 3. Execute Node
        result = supervisor_node(state)
        
        # 4. Assert Routing Decision
        assert result["next"] == "FINISH"
        # In the graph, this "FINISH" maps to END

def test_supervisor_routing_ambiguous_content():
    """
    Test routing logic: Robustness check. 
    If LLM returns text containing the keyword, it should still route correctly.
    """
    state = MarketingState(messages=[], next="")

    with patch("marketing_team.nodes.supervisor_chain") as mock_chain:
        # Simulate verbose LLM output
        mock_chain.invoke.return_value = AIMessage(content="I think the CampaignManager should handle this next.")
        
        result = supervisor_node(state)
        
        # Our logic checks `if "CampaignManager" in next_agent:`
        assert result["next"] == "CampaignManager"

