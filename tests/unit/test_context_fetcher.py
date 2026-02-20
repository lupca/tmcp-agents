import pytest
from unittest.mock import patch, AsyncMock
from app.services.context_fetcher import fetch_campaign_context

@pytest.mark.asyncio
async def test_fetch_campaign_context_success():
    # Mock execute_mcp_tool to return predefined results based on the collection
    async def mock_execute_mcp_tool(tool_name, args):
        collection = args.get("collection")
        class MockResult:
            def __init__(self, text):
                class Content:
                    def __init__(self, t):
                        self.text = t
                self.content = [Content(text)]

        if collection == "marketing_campaigns":
            return MockResult('{"id": "camp1", "worksheet_id": "ws1", "brand_id": "brand1", "persona_id": "persona1"}')
        elif collection == "worksheets":
            return MockResult('{"id": "ws1", "name": "Test Worksheet"}')
        elif collection == "brand_identities":
            return MockResult('{"id": "brand1", "brand_name": "Test Brand"}')
        elif collection == "ideal_customer_profiles":
            return MockResult('{"id": "persona1", "persona_name": "Test Persona"}')
        return MockResult('{}')

    with patch("app.services.context_fetcher.execute_mcp_tool", side_effect=mock_execute_mcp_tool):
        context, errors = await fetch_campaign_context("camp1")

        assert not errors
        assert context["campaign"]["id"] == "camp1"
        assert context["worksheet"]["name"] == "Test Worksheet"
        assert context["brandIdentity"]["brand_name"] == "Test Brand"
        assert context["customerProfile"]["persona_name"] == "Test Persona"

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
        assert context["brandIdentity"] == {}
        assert context["customerProfile"] == {}
