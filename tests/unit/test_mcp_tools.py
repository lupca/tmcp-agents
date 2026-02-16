
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.tools.mcp_bridge import list_collections, get_record, create_record, execute_mcp_tool

# Mock basic MCP Types
class MockTextContent:
    def __init__(self, text):
        self.text = text

class MockContent:
    def __init__(self, text):
        self.type = "text"
        self.text = text

class MockToolResult:
    def __init__(self, text):
        self.content = [MockContent(text)]

@pytest.mark.asyncio
async def test_mcp_tool_execution_success():
    """Test successful execution of an MCP tool wrapper."""
    mock_data = '{"items": [{"id": "1", "name": "Test Collection"}]}'
    
    with patch("app.tools.mcp_bridge.execute_mcp_tool") as mock_execute:
        mock_execute.return_value = MockToolResult(mock_data)
        
        result = await list_collections.ainvoke({})
        
        assert result == mock_data
        mock_execute.assert_called_once_with("list_collections", {})

@pytest.mark.asyncio
async def test_mcp_create_record_json_parsing():
    """Test JSON parsing logic in create_record wrapper."""
    
    # 1. Valid Dict Input
    with patch("app.tools.mcp_bridge.execute_mcp_tool") as mock_execute:
        mock_execute.return_value = MockToolResult("Created")
        
        await create_record.ainvoke({"collection": "test", "data_json": {"field": "value"}})
        
        mock_execute.assert_called_with("create_record", {"collection": "test", "data": {"field": "value"}})

    # 2. Valid JSON String Input
    with patch("app.tools.mcp_bridge.execute_mcp_tool") as mock_execute:
        mock_execute.return_value = MockToolResult("Created")
        
        await create_record.ainvoke({"collection": "test", "data_json": '{"field": "value"}'})
        
        mock_execute.assert_called_with("create_record", {"collection": "test", "data": {"field": "value"}})
        
    # 3. Invalid JSON String
    result = await create_record.ainvoke({"collection": "test", "data_json": "{invalid json"})
    assert "Error parsing data_json" in result

@pytest.mark.asyncio
async def test_mcp_connection_error_handling():
    """Test handling of connection errors to MCP server."""
    
    # Simulate execute_mcp_tool raising an exception (e.g. connection refused)
    with patch("app.tools.mcp_bridge.sse_client", side_effect=ConnectionError("Connection refused")):
        # We need to test the actual execute_mcp_tool function, not the wrapper, 
        # or verify the wrapper lets the exception propagate or handles it.
        # Looking at mcp_bridge.py, wrappers await execute_mcp_tool. 
        # Integration test style:
        
        with pytest.raises(ConnectionError):
            await execute_mcp_tool("test_tool", {})

@pytest.mark.asyncio
async def test_mcp_server_error_response():
    """Test handling when MCP server returns an error or unexpected format."""
    
    # If MCP server returns an error result structure
    with patch("app.tools.mcp_bridge.execute_mcp_tool") as mock_execute:
        # Mocking an exception raised by the underlying MCP client call
        mock_execute.side_effect = Exception("Tool execution failed")
        
        with pytest.raises(Exception) as excinfo:
            await list_collections.ainvoke({})
        
        assert "Tool execution failed" in str(excinfo.value)
