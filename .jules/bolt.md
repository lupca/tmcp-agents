## 2024-05-18 - [Parallelize MCP tool fetching]
**Learning:** Sequential MCP data operations inside an async generator (e.g. `execute_mcp_tool` inside a loop) create N+1 bottlenecks.
**Action:** Always extract single-record creation or fetching logic into a helper coroutine and execute the batch concurrently using `asyncio.gather`.
