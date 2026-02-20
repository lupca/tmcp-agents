from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import EditorBrandGuardianState
from .nodes import retriever_node, validator_node, evaluator_node, saver_node

workflow = StateGraph(EditorBrandGuardianState)

workflow.add_node("Retriever", retriever_node)
workflow.add_node("Validator", validator_node)
workflow.add_node("Evaluator", evaluator_node)
workflow.add_node("Saver", saver_node)

workflow.add_edge(START, "Retriever")
workflow.add_edge("Retriever", "Validator")
workflow.add_edge("Validator", "Evaluator")
workflow.add_edge("Saver", END)


def determine_next_node(state: EditorBrandGuardianState):
    next_node = state.get("next_node", "FINISH")
    if next_node == "FINISH":
        return "Saver"
    return next_node


workflow.add_conditional_edges(
    "Evaluator",
    determine_next_node,
    {
        "Validator": "Validator",
        "Saver": "Saver",
        END: END,
    },
)

memory = MemorySaver()
editor_brand_guardian_graph = workflow.compile(checkpointer=memory)
