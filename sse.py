import json


def sse_event(event_type: str, **kwargs) -> str:
    """Format a Server-Sent Event data line.

    Usage:
        yield sse_event("status", status="thinking", agent="Supervisor")
        yield sse_event("chunk", content="Hello")
        yield sse_event("done")
        yield sse_event("error", error="Something went wrong")
    """
    payload = {"type": event_type, **kwargs}
    return f"data: {json.dumps(payload)}\n\n"
