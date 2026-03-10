## 2024-05-19 - Context Fetcher Optimization
**Learning:** Sequential MCP tool calls in Python services create severe N+1 bottlenecks.
**Action:** Always group independent MCP tool calls (like fetching worksheet & product concurrently, then brand & customer concurrently) using `asyncio.gather` to significantly reduce latency while preserving execution chains.
