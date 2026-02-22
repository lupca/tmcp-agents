## 2024-05-23 - Parallel Data Fetching in Streaming Responses
**Learning:** Sequential await calls in streaming endpoints unnecessarily block execution. Using `asyncio.create_task()` to start all I/O operations immediately, then awaiting them sequentially in the yield loop, allows for parallel execution while preserving the exact order of status events for the frontend.
**Action:** Identify other streaming generators (e.g. `brand_identity_event_generator`, `customer_profile_event_generator`) where independent data fetches can be parallelized using this pattern.
