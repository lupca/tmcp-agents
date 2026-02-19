from typing import Annotated, Dict, List, TypedDict, Any, Optional
from langgraph.graph.message import add_messages


class MasterContentState(TypedDict):
    """
    State for the Master Content generation agent.
    
    Flow: Retriever → Evaluator → Generator → Evaluator → END
    """
    messages: Annotated[List[Any], add_messages]
    
    # Input
    campaign_id: str
    workspace_id: str
    language: str
    
    # Context fetched by Retriever
    context_data: Dict[str, Any]
    
    # Generated output
    generated_content: Optional[Dict[str, Any]]
    
    # Evaluator routing
    feedback: str
    next_node: str
