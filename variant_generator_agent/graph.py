from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import VariantGeneratorState
from .nodes import (
    retriever_node,
    generator_node,
    evaluator_node,
    saver_node,
)

"""
Variant Generator Agent Graph

Flow (Parallelized):
  START → Retriever → Evaluator (Context Check) ─┬─ Generator (Parallel) → Saver → END
                                                 │
                                                 └── FINISH (Error) → END
"""

# 1. Create the graph
workflow = StateGraph(VariantGeneratorState)

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

# Generator → Saver (All variants generated in parallel, move to save)
workflow.add_edge("Generator", "Saver")

# Saver → END
workflow.add_edge("Saver", END)


# Conditional edges from Evaluator (Context Check)
def determine_next_node(state: VariantGeneratorState):
    next_node = state.get("next_node", "FINISH")

    if next_node == "Generator":
        return "Generator"

    # If context missing, finish
    return END


workflow.add_conditional_edges(
    "Evaluator",
    determine_next_node,
    {
        "Generator": "Generator",
        END: END,
    },
)

# 4. Compile the graph
memory = MemorySaver()
variant_generator_graph = workflow.compile(checkpointer=memory)
