## 2024-05-24 - Overzealous Linting of Entry Points
**Learning:** Running `ruff check --fix` removed a critical import (`from marketing_team.graph import marketing_graph as app_graph`) in `agent.py` because it appeared "unused". However, `agent.py` serves as a LangGraph module entry point and is explicitly imported in tests.
**Action:** Never run automated linter fixes without manually verifying changes to root-level files or files acting purely as re-exports.

## 2024-05-24 - Parallel MCP Fetching UX Pattern
**Learning:** When moving sequential data fetching into a concurrent `asyncio.gather` block, the SSE status events that update the UI must be yielded *before* the gather call. If emitted inside the tasks or after, the UI won't reflect the start of the fetching process correctly, leading to perceived unresponsiveness.
**Action:** Always emit all "starting task X" status events sequentially immediately before awaiting the parallelized tasks.