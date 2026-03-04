## 2024-05-01 - Parallelizing MCP Data Fetching
**Learning:** Sequential MCP data operations create N+1 bottlenecks when resolving relationships (like Worksheet -> Brand & ICP).
**Action:** Always extract single-record creation or fetching logic into a helper coroutine and execute the batch concurrently using `asyncio.gather` when operations are independent.
