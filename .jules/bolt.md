## 2026-02-18 - [Sync LLM Nodes Block Event Loop]
**Learning:** Synchronous LLM calls in LangGraph nodes (using `invoke`) block the main event loop, especially when served via FastAPI, degrading concurrency.
**Action:** Convert sync nodes to `async` using `ainvoke` for all I/O bound operations.

## 2026-02-18 - [Robust Testing in conftest.py]
**Learning:** `conftest.py` importing heavy dependencies directly can prevent unit tests from running in restricted environments.
**Action:** Wrap optional imports in `conftest.py` with `try-except` blocks to allow partial test execution.
