from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import AngleStrategistState
from .nodes import retriever_node, generator_node, evaluator_node, saver_node

workflow = StateGraph(AngleStrategistState)

workflow.add_node("Retriever", retriever_node)
workflow.add_node("Evaluator", evaluator_node)
workflow.add_node("Generator", generator_node)
workflow.add_node("Saver", saver_node)

workflow.add_edge(START, "Retriever")
workflow.add_edge("Retriever", "Evaluator")
workflow.add_edge("Generator", "Evaluator")
workflow.add_edge("Saver", END)


def determine_next_node(state: AngleStrategistState):
    next_node = state.get("next_node", "FINISH")
    generated_angles = state.get("generated_angles")

    if next_node == "FINISH":
        if generated_angles and not (isinstance(generated_angles, list) and generated_angles[0].get("_parse_error")):
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

memory = MemorySaver()
angle_strategist_graph = workflow.compile(checkpointer=memory)
