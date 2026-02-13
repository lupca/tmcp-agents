from typing import Annotated, List, TypedDict, Union
from langgraph.graph.message import add_messages

class MarketingState(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[List, add_messages]
    # The next node to route to
    next: str
