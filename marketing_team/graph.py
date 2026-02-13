from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import MarketingState
from .nodes import (
    supervisor_node,
    strategist_node,
    campaign_manager_node,
    researcher_node,
    content_creator_node
)

# 1. Create the graph
workflow = StateGraph(MarketingState)

# 2. Add nodes
workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("Strategist", strategist_node)
workflow.add_node("CampaignManager", campaign_manager_node)
workflow.add_node("Researcher", researcher_node)
workflow.add_node("ContentCreator", content_creator_node)

# 3. Add edges
# The supervisor decides where to go next
workflow.add_edge(START, "Supervisor")

# Conditional edges from Supervisor
workflow.add_conditional_edges(
    "Supervisor",
    lambda state: state["next"],
    {
        "Strategist": "Strategist",
        "CampaignManager": "CampaignManager",
        "Researcher": "Researcher",
        "ContentCreator": "ContentCreator",
        "FINISH": END
    }
)

# All workers return to Supervisor
workflow.add_edge("Strategist", "Supervisor")
workflow.add_edge("CampaignManager", "Supervisor")
workflow.add_edge("Researcher", "Supervisor")
workflow.add_edge("ContentCreator", "Supervisor")

# 4. Compile the graph
memory = MemorySaver()
marketing_graph = workflow.compile(checkpointer=memory)
