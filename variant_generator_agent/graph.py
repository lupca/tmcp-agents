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

Flow:
  START → Retriever → Evaluator ─┬─ Generator → Evaluator ─┬─ Saver → END
                                  │                          │
                                  └── FINISH (error) → END   ├── RETRY → Generator
                                                             └── Next platform → Generator
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

# Generator → Evaluator (evaluate generated variant)
workflow.add_edge("Generator", "Evaluator")

# Saver → END
workflow.add_edge("Saver", END)


# Conditional edges from Evaluator
def determine_next_node(state: VariantGeneratorState):
    next_node = state.get("next_node", "FINISH")

    if next_node == "FINISH":
        generated_variants = state.get("generated_variants", [])
        if generated_variants:
            return "Saver"
        return END

    if next_node == "Generator":
        return "Generator"

    return END


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
variant_generator_graph = workflow.compile(checkpointer=memory)
