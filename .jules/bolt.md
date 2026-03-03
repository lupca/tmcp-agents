## 2024-05-19 - MCP Tool Execution Bottleneck
**Learning:** Sequential MCP data operations create N+1 bottlenecks.
**Action:** Always extract single-record creation or fetching logic into a helper coroutine and execute the batch concurrently using `asyncio.gather`.
