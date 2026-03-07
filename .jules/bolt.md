
## 2024-03-07 - Test environment lacks dependencies
**Learning:** The development environment lacks pre-installed Python dependencies like `pytest`, `langchain_core`, `mcp`, etc., making it impossible to run the full test suite without extensive mocking, which is noted in memory.
**Action:** Relied on `python3 -m py_compile` to check syntax, and will mention this environmental limitation.
