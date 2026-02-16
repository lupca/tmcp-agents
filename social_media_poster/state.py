from typing import Annotated, Dict, List, TypedDict, Any
from langgraph.graph.message import add_messages

class SocialMediaState(TypedDict):
    """
    Represents the state of the social media post generation flow.
    """
    messages: Annotated[List[Any], add_messages]
    context_data: Dict[str, Any]
    generated_post: str
    feedback: str
    next_node: str
