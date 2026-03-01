import pytest
from unittest.mock import patch
from app.services.context_fetcher import fetch_campaign_context
import json

@pytest.mark.asyncio
async def test_fetch_campaign_context_success():
    # Mock execute_mcp_tool to return predefined results based on the collection
    # The new context_fetcher uses expand on the campaign fetch to get product->brand
    async def mock_execute_mcp_tool(tool_name, args):
        collection = args.get("collection")
        class MockResult:
            def __init__(self, text):
                class Content:
                    def __init__(self, t):
                        self.text = t
                self.content = [Content(text)]

        if collection == "marketing_campaigns":
            # Campaign with product_id and worksheet_id, with expand data
            campaign_data = {
                "id": "camp1",
                "worksheet_id": "ws1",
                "product_id": "prod1",
                "expand": {
                    "worksheet_id": {"id": "ws1", "name": "Test Worksheet", "brandRefs": ["brand1"], "customerRefs": ["persona1"]},
                    "product_id": {
                        "id": "prod1", "name": "Test Product", "usp": "Best product",
                        "key_features": ["Feature 1"], "key_benefits": ["Benefit 1"],
                        "expand": {
                            "brand_id": {"id": "brand1", "brand_name": "Test Brand"}
                        }
                    }
                }
            }
            return MockResult(json.dumps(campaign_data))
        elif collection == "customer_personas":
            return MockResult('{"id": "persona1", "persona_name": "Test Persona"}')
        return MockResult('{}')

    with patch("app.services.context_fetcher.execute_mcp_tool", side_effect=mock_execute_mcp_tool):
        context, errors = await fetch_campaign_context("camp1")

        assert not errors
        assert context["campaign"]["id"] == "camp1"
        assert context["worksheet"]["name"] == "Test Worksheet"
        assert context["brandIdentity"]["brand_name"] == "Test Brand"
        assert context["product"]["name"] == "Test Product"
        assert context["customerProfile"]["persona_name"] == "Test Persona"


@pytest.mark.asyncio
async def test_fetch_campaign_context_no_product_fallback_worksheet_brand():
    """When no product_id, brand should be fetched from worksheet.brandRefs."""
    async def mock_execute_mcp_tool(tool_name, args):
        collection = args.get("collection")
        class MockResult:
            def __init__(self, text):
                class Content:
                    def __init__(self, t):
                        self.text = t
                self.content = [Content(text)]

        if collection == "marketing_campaigns":
            campaign_data = {
                "id": "camp2",
                "worksheet_id": "ws2",
                "expand": {
                    "worksheet_id": {"id": "ws2", "name": "Worksheet 2", "brandRefs": ["brand2"], "customerRefs": []}
                }
            }
            return MockResult(json.dumps(campaign_data))
        elif collection == "brand_identities":
            return MockResult('{"id": "brand2", "brand_name": "Fallback Brand"}')
        return MockResult('{}')

    with patch("app.services.context_fetcher.execute_mcp_tool", side_effect=mock_execute_mcp_tool):
        context, errors = await fetch_campaign_context("camp2")

        assert context["campaign"]["id"] == "camp2"
        assert context["brandIdentity"]["brand_name"] == "Fallback Brand"
        assert context["product"] == {}
        assert context["customerProfile"] == {}

@pytest.mark.asyncio
async def test_fetch_campaign_context_campaign_not_found():
    async def mock_execute_mcp_tool(tool_name, args):
        class MockResult:
            def __init__(self, text):
                class Content:
                    def __init__(self, t):
                        self.text = t
                self.content = [Content(text)]
        return MockResult('Error: Record not found')

    with patch("app.services.context_fetcher.execute_mcp_tool", side_effect=mock_execute_mcp_tool):
        context, errors = await fetch_campaign_context("camp1")

        assert "campaign" in errors
        assert errors["campaign"] == "Error: Record not found"
        assert context["campaign"] == {}
        assert context["worksheet"] == {}
        assert context["product"] == {}
        assert context["brandIdentity"] == {}
        assert context["customerProfile"] == {}
