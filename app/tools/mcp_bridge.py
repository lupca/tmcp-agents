import os
import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

# Helper to run a tool via SSE
from mcp.client.sse import sse_client
from contextvars import ContextVar

auth_token_var: ContextVar[str] = ContextVar("auth_token", default="")

def parse_mcp_result(result: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse MCP tool result. Returns (data, error_msg)."""
    if not result or not hasattr(result, "content") or not result.content:
        return None, "Empty or invalid result from MCP"
        
    text = result.content[0].text
    if text.startswith("Error:"):
        return None, text
    try:
        return json.loads(text), None
    except (json.JSONDecodeError, ValueError) as e:
        return None, f"JSON parse error: {e}. Raw: {text[:200]}"

async def execute_mcp_tool(tool_name: str, arguments: dict) -> Any:
    # URL of the standalone MCP server
    sse_url = os.getenv("MCP_SERVER_URL", "http://localhost:7999/sse")

    token = auth_token_var.get()
    if token and tool_name in ["get_record", "list_records", "create_record", "update_record", "delete_record"] and "auth_token" not in arguments:
        arguments["auth_token"] = token

    async with sse_client(sse_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return result

async def execute_mcp_read_resource(uri: str) -> Any:
    # URL of the standalone MCP server
    sse_url = os.getenv("MCP_SERVER_URL", "http://localhost:7999/sse")

    async with sse_client(sse_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.read_resource(uri)
            return result

# Tool Wrappers
from langchain_core.tools import tool

@tool
async def list_collections() -> str:
    """Lists all available collections in PocketBase."""
    result = await execute_mcp_tool("list_collections", {})
    return result.content[0].text

@tool
async def get_collection_schema(collection: str) -> str:
    """Gets the schema (fields and types) for a specific collection."""
    result = await execute_mcp_tool("get_collection_schema", {"collection": collection})
    return result.content[0].text

@tool
async def list_records(collection: str, page: int = 1, per_page: int = 30, filter: str = "") -> str:
    """Lists records in a collection with pagination and filtering."""
    result = await execute_mcp_tool("list_records", {"collection": collection, "page": page, "per_page": per_page, "filter": filter})
    return result.content[0].text

@tool
async def get_record(collection: str, record_id: str) -> str:
    """Retrieves a single record by its ID."""
    result = await execute_mcp_tool("get_record", {"collection": collection, "record_id": record_id})
    return result.content[0].text

import json

@tool
async def create_record(collection: str, data_json: str | dict) -> str:
    """Creates a new record in the specified collection. data_json must be a valid JSON string or object representing the record data."""
    if isinstance(data_json, dict):
        data = data_json
    else:
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError as e:
            return f"Error parsing data_json: {e}"
        except TypeError as e:
            return f"Error processing data_json (type {type(data_json)}): {e}"
        
    result = await execute_mcp_tool("create_record", {"collection": collection, "data": data})
    return result.content[0].text

@tool
async def update_record(collection: str, record_id: str, data_json: str | dict) -> str:
    """Updates an existing record. data_json must be a valid JSON string or object representing the data to update."""
    if isinstance(data_json, dict):
        data = data_json
    else:
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError as e:
            return f"Error parsing data_json: {e}"
        except TypeError as e:
            return f"Error processing data_json (type {type(data_json)}): {e}"

    result = await execute_mcp_tool("update_record", {"collection": collection, "record_id": record_id, "data": data})
    return result.content[0].text

@tool
async def delete_record(collection: str, record_id: str) -> str:
    """Deletes a record."""
    result = await execute_mcp_tool("delete_record", {"collection": collection, "record_id": record_id})
    return result.content[0].text

@tool
async def read_resource(uri: str) -> str:
    """Reads a resource from the MCP server.
    Supported URIs:
    - pocketbase:// : Lists all available collections
    - pocketbase://{collection_name}/schema : Gets the schema for a collection
    - pocketbase://{collection_name}/{record_id} : Gets a specific record
    """
    try:
        # The result object has a 'contents' attribute which is a list of ResourceContent
        result = await execute_mcp_read_resource(uri)
        if result.contents and len(result.contents) > 0:
            return result.contents[0].text
        return "Resource empty or not found."
    except Exception as e:
        return f"Error reading resource {uri}: {e}"

# Export all tools
all_tools = [
    list_collections,
    get_collection_schema,
    list_records,
    get_record,
    create_record,
    update_record,
    delete_record,
    read_resource
]

