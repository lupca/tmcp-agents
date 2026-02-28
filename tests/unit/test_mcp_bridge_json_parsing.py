import asyncio
import json
import sys
from unittest.mock import AsyncMock, patch, MagicMock
from types import ModuleType

# Mock dependencies before importing mcp_bridge
def mock_dependencies():
    # Mock mcp
    mcp_mock = ModuleType("mcp")
    mcp_mock.ClientSession = MagicMock()
    mcp_mock.StdioServerParameters = MagicMock()
    sys.modules["mcp"] = mcp_mock

    mcp_client_mock = ModuleType("mcp.client")
    sys.modules["mcp.client"] = mcp_client_mock

    mcp_client_stdio_mock = ModuleType("mcp.client.stdio")
    mcp_client_stdio_mock.stdio_client = MagicMock()
    sys.modules["mcp.client.stdio"] = mcp_client_stdio_mock

    mcp_client_sse_mock = ModuleType("mcp.client.sse")
    mcp_client_sse_mock.sse_client = MagicMock()
    sys.modules["mcp.client.sse"] = mcp_client_sse_mock

    # Mock langchain_core.tools
    langchain_core_tools_mock = ModuleType("langchain_core.tools")
    def dummy_tool(func):
        return func
    langchain_core_tools_mock.tool = dummy_tool
    sys.modules["langchain_core"] = ModuleType("langchain_core")
    sys.modules["langchain_core.tools"] = langchain_core_tools_mock

mock_dependencies()

# Now import the tools from mcp_bridge
from mcp_bridge import update_record, create_record

# --- Tests for update_record ---

def test_update_record_invalid_json():
    """Test update_record with an invalid JSON string."""
    result = asyncio.run(update_record("test_col", "test_id", "{invalid json}"))
    assert "Error parsing data_json:" in result
    assert "Expecting property name enclosed in double quotes" in result

def test_update_record_invalid_type():
    """Test update_record with an invalid input type (not string or dict)."""
    result = asyncio.run(update_record("test_col", "test_id", 123))
    assert "Error processing data_json (type <class 'int'>):" in result

@patch("mcp_bridge.execute_mcp_tool", new_callable=AsyncMock)
def test_update_record_valid_json_string(mock_execute):
    """Test update_record with a valid JSON string."""
    mock_result = MagicMock()
    mock_result.content = [MagicMock(text="success_update")]
    mock_execute.return_value = mock_result

    result = asyncio.run(update_record("test_col", "test_id", '{"field": "value"}'))

    assert result == "success_update"
    mock_execute.assert_called_once_with("update_record", {
        "collection": "test_col",
        "record_id": "test_id",
        "data": {"field": "value"}
    })

@patch("mcp_bridge.execute_mcp_tool", new_callable=AsyncMock)
def test_update_record_valid_dict(mock_execute):
    """Test update_record with a valid dictionary."""
    mock_result = MagicMock()
    mock_result.content = [MagicMock(text="success_update_dict")]
    mock_execute.return_value = mock_result

    result = asyncio.run(update_record("test_col", "test_id", {"field": "value"}))

    assert result == "success_update_dict"
    mock_execute.assert_called_once_with("update_record", {
        "collection": "test_col",
        "record_id": "test_id",
        "data": {"field": "value"}
    })

# --- Tests for create_record ---

def test_create_record_invalid_json():
    """Test create_record with an invalid JSON string."""
    result = asyncio.run(create_record("test_col", "{invalid json}"))
    assert "Error parsing data_json:" in result
    assert "Expecting property name enclosed in double quotes" in result

def test_create_record_invalid_type():
    """Test create_record with an invalid input type (not string or dict)."""
    result = asyncio.run(create_record("test_col", [1, 2, 3]))
    assert "Error processing data_json (type <class 'list'>):" in result

@patch("mcp_bridge.execute_mcp_tool", new_callable=AsyncMock)
def test_create_record_valid_json_string(mock_execute):
    """Test create_record with a valid JSON string."""
    mock_result = MagicMock()
    mock_result.content = [MagicMock(text="success_create")]
    mock_execute.return_value = mock_result

    result = asyncio.run(create_record("test_col", '{"foo": "bar"}'))

    assert result == "success_create"
    mock_execute.assert_called_once_with("create_record", {
        "collection": "test_col",
        "data": {"foo": "bar"}
    })

@patch("mcp_bridge.execute_mcp_tool", new_callable=AsyncMock)
def test_create_record_valid_dict(mock_execute):
    """Test create_record with a valid dictionary."""
    mock_result = MagicMock()
    mock_result.content = [MagicMock(text="success_create_dict")]
    mock_execute.return_value = mock_result

    result = asyncio.run(create_record("test_col", {"foo": "bar"}))

    assert result == "success_create_dict"
    mock_execute.assert_called_once_with("create_record", {
        "collection": "test_col",
        "data": {"foo": "bar"}
    })
