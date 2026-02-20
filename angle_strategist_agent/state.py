from typing import Annotated, Dict, List, TypedDict, Any, Optional
from langgraph.graph.message import add_messages


class AngleStrategistState(TypedDict):
    messages: Annotated[List[Any], add_messages]

    campaign_id: str
    workspace_id: str
    language: str
    num_angles: int

    context_data: Dict[str, Any]
    generated_angles: Optional[List[Dict[str, Any]]]

    feedback: str
    next_node: str
