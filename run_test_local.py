import asyncio
import sys
import os
import json
from unittest.mock import MagicMock, patch
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.unit.test_marketing_strategy_service import _collect_events, MOCK_WORKSHEET, MOCK_BRAND, MOCK_ICP, MOCK_STRATEGY
from app.services.strategy import marketing_strategy_event_generator

async def main():
    mock_ws_result = MagicMock()
    mock_ws_result.content = [MagicMock(text=json.dumps(MOCK_WORKSHEET))]
    mock_brand_result = MagicMock()
    mock_brand_result.content = [MagicMock(text=json.dumps(MOCK_BRAND))]
    mock_icp_result = MagicMock()
    mock_icp_result.content = [MagicMock(text=json.dumps(MOCK_ICP))]
    mock_product_result = MagicMock()
    mock_product_result.content = [MagicMock(text=json.dumps({"name": "Product 1"}))]

    async def mock_execute_mcp_tool(tool_name, args):
        collection = args.get("collection")
        if collection == "worksheets": return mock_ws_result
        elif collection == "brand_identities": return mock_brand_result
        elif collection == "ideal_customer_profiles": return mock_icp_result
        elif collection == "products_services": return mock_product_result
        raise ValueError(f"Unexpected collection: {collection}")

    mock_chunk = MagicMock()
    mock_chunk.content = json.dumps(MOCK_STRATEGY)
    async def mock_astream(*args, **kwargs): yield mock_chunk
    mock_llm = MagicMock()
    mock_llm.astream = mock_astream

    with patch("app.services.strategy.execute_mcp_tool", side_effect=mock_execute_mcp_tool), patch("app.services.strategy.get_ollama_llm", return_value=mock_llm):
        events = []
        async for event in marketing_strategy_event_generator("ws_1", "awareness", "prod_1", "Increase", "English"):
            events.append(event)
        
        parsed = _collect_events(events)
        for e in parsed:
            print(e)

asyncio.run(main())
