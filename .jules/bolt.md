## 2024-05-28 - Async Nodes for I/O Performance in LangGraph
**Learning:** Synchronous nodes in LangGraph that perform I/O operations (like LLM calls via `chain.invoke`) block the Python event loop, significantly degrading overall performance in async applications like FastAPI, especially when streaming events.
**Action:** Always convert LangGraph nodes performing I/O to `async def` and use the async variants of invocation methods (e.g., `await chain.ainvoke(state, config)`). Remember to pass `config: RunnableConfig` to ensure tracing and thread IDs propagate correctly.
