from typing import Annotated, Dict, List, TypedDict, Any, Optional
from langgraph.graph.message import add_messages


class EditorBrandGuardianState(TypedDict):
    messages: Annotated[List[Any], add_messages]

    campaign_id: str
    workspace_id: str
    language: str

    master_contents: List[Dict[str, Any]]
    variants: List[Dict[str, Any]]

    brand_context: Dict[str, Any]
    validation_results: Optional[Dict[str, Any]]

    feedback: str
    next_node: str
