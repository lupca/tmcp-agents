
## 2024-05-24 - N+1 Bottlenecks in Async Generators
**Learning:** Sequential MCP data fetches inside a loop inside an `AsyncGenerator` cause significant N+1 wait times. Furthermore, when converting this to `asyncio.gather`, `yield` statements cannot be placed inside the awaited coroutines.
**Action:** Always extract the individual fetch logic into a standalone coroutine, run them via `asyncio.gather()`, and emit all UI `yield` events *prior* to awaiting the gathered tasks to ensure smooth UI progress.
