from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import SocialMediaState
from .nodes import (
    content_retriever_node,
    post_generator_node,
    evaluator_node
)

# 1. Create the graph
workflow = StateGraph(SocialMediaState)

# 2. Add nodes
workflow.add_node("Retriever", content_retriever_node)
workflow.add_node("PostGenerator", post_generator_node)
workflow.add_node("Evaluator", evaluator_node)

# 3. Add edges

# Start -> R
workflow.add_edge(START, "Retriever")

# R -> E
workflow.add_edge("Retriever", "Evaluator")

# G -> E
workflow.add_edge("PostGenerator", "Evaluator")

# Conditional Edges from Evaluator
def determine_next_node(state: SocialMediaState):
    next_node = state.get("next_node")
    if next_node == "FINISH":
        return END
    return next_node

workflow.add_conditional_edges(
    "Evaluator",
    determine_next_node,
    {
        "Retriever": "Retriever",
        "PostGenerator": "PostGenerator",
        END: END
    }
)

# 4. Compile the graph
memory = MemorySaver()
social_media_graph = workflow.compile(checkpointer=memory)
