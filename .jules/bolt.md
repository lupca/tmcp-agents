## 2024-05-25 - Parallelize MCP fetch in SSE Generators
**Learning:** Sequential MCP tool calls in SSE generator loops (like `worksheet.py`) create an N+1 bottleneck. Parallelizing with `asyncio.gather` reduces latency.
**Action:** Always extract single-record logic to an async helper and use `asyncio.gather` for arrays of IDs. Ensure `yield` statements for 'status' events occur before the `gather` call to maintain UI updates.
