## 2024-05-14 - Parallelize MCP Data Creation with asyncio.gather
**Learning:** Found an N+1 performance bottleneck in `app/services/content_briefs.py` where creating 24 records (4 stages * 6 angles) caused 24 sequential API calls to the database over MCP (`execute_mcp_tool("create_record", ...)`), causing high latency.
**Action:** When saving multiple entities to a database via MCP, always extract the single-record creation logic into a helper coroutine and run the whole batch concurrently using `await asyncio.gather(*save_tasks)` to maximize throughput.
