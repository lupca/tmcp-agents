from typing import Annotated, Dict, List, TypedDict, Any, Optional
from langgraph.graph.message import add_messages


class VariantGeneratorState(TypedDict):
    """
    State for the Platform Variant generation agent.

    Flow: Retriever → Evaluator → Generator (per platform) → Evaluator → Saver → END
    """
    messages: Annotated[List[Any], add_messages]

    # Input
    master_content_id: str
    platforms: List[str]
    workspace_id: str
    language: str

    # Context fetched by Retriever
    context_data: Dict[str, Any]

    # Generation tracking
    current_platform_index: int
    generated_variants: List[Dict[str, Any]]  # accumulated results per platform
    current_variant: Optional[Dict[str, Any]]  # latest single-platform result

    # Evaluator routing
    feedback: str
    next_node: str
