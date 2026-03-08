## 2024-05-24 - Parallel MCP Fetching with asyncio.gather
**Learning:** Sequential MCP data fetches can cause N+1 query bottlenecks and increase agent latency significantly, specifically when fetching context components that have dependency chains.
**Action:** Use a phased `asyncio.gather` approach for data fetching: Phase 1 (Worksheet, Product) runs concurrently after the initial Campaign fetch, and Phase 2 (Brand, Customer) runs concurrently after Phase 1 to respect data dependencies and minimize latency.
