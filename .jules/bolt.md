
## 2024-03-01 - Parallelize MCP Data Fetching in Worksheet Generation
**Learning:** Sequential MCP fetching inside generator loops (e.g., `worksheet_event_generator`) is an N+1 query anti-pattern specific to this codebase that significantly inflates latency, especially since UI "fetching" status events can be emitted up-front without waiting.
**Action:** Always inspect `.py` files using `astream_events` generators for sequential `execute_mcp_tool` calls in loops, and refactor them to use `asyncio.gather` for parallel fetching while sequentially emitting `status` SSE events up-front.
