## 2024-05-23 - Parallelizing Context Retrieval
**Learning:** The application frequently retrieves multiple independent context records (Brand, ICP, Product) after an initial dependent fetch (Worksheet). Sequential fetching adds significant latency (sum of RTTs). Parallelizing these with `asyncio.gather` drastically reduces wait time (max of RTTs).
**Action:** Look for "fan-out" data fetching patterns in other services (e.g., content generation) and apply `asyncio.gather` with robust error handling wrappers.
