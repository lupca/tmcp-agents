## 2024-03-15 - [Bolt: N+1 Optimization in Generator]
**Learning:** Found an N+1 bottleneck pattern during MCP tool execution within a nested loop in a generator (`content_briefs.py`). Using `asyncio.gather` for parallelizing data creation while isolating generator yields prevents the loop overhead.
**Action:** When working with generators that emit SSE events, yield state transitions or status updates synchronously first, collect inner task coroutines mapping to MCP calls, then execute with `asyncio.gather(*tasks)` to prevent network I/O from bottlenecking the generator flow.
