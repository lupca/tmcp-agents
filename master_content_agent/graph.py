from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import MasterContentState
from .nodes import (
    retriever_node,
    generator_node,
    evaluator_node,
    saver_node,
)

"""
Master Content Agent Graph

Flow:
  START → Retriever → Evaluator ─┬─ Generator → Evaluator ─┬─ Saver → END
                                  │                          │
                                  └── FINISH (error) → END   └── RETRY → Generator
"""

# 1. Create the graph
workflow = StateGraph(MasterContentState)

# 2. Add nodes
workflow.add_node("Retriever", retriever_node)
workflow.add_node("Evaluator", evaluator_node)
workflow.add_node("Generator", generator_node)
workflow.add_node("Saver", saver_node)

# 3. Add edges

# START → Retriever
workflow.add_edge(START, "Retriever")

# Retriever → Evaluator (evaluate context)
workflow.add_edge("Retriever", "Evaluator")

# Generator → Evaluator (evaluate generated content)
workflow.add_edge("Generator", "Evaluator")

# Saver → END
workflow.add_edge("Saver", END)


# Conditional edges from Evaluator
def determine_next_node(state: MasterContentState):
    next_node = state.get("next_node", "FINISH")
    generated_content = state.get("generated_content")

    if next_node == "FINISH":
        # If we have approved content, save it; otherwise end with error
        if generated_content and not generated_content.get("_parse_error"):
            return "Saver"
        return END
    return next_node


workflow.add_conditional_edges(
    "Evaluator",
    determine_next_node,
    {
        "Generator": "Generator",
        "Saver": "Saver",
        END: END,
    },
)

# 4. Compile the graph
memory = MemorySaver()
master_content_graph = workflow.compile(checkpointer=memory)
