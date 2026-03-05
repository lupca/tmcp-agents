## 2024-03-05 - Sequencing SSE Events with asyncio.gather
**Learning:** When refactoring sequential tool calls (like MCP fetches) into parallel `asyncio.gather` blocks to resolve N+1 queries, SSE progress events inside the original sequential loops are lost or happen all at once.
**Action:** Always emit the 'start' status SSE events sequentially *before* executing the `asyncio.gather` block to maintain immediate UI responsiveness and reflect the system's intent to the user, even while the actual fetches happen concurrently.
