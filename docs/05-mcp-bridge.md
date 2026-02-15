# 🔌 MCP Bridge — Tool Integration

> **File chính:** `mcp_bridge.py`

---

## 1. Tổng quan

**MCP Bridge** là lớp trung gian chuyển đổi giữa hai protocol:

- **LangChain Tools** (phía agents sử dụng)
- **MCP Protocol** (phía PocketBase server)

Nó wrap các MCP tool calls thành LangChain `@tool` functions để LLM có thể gọi trực tiếp.

---

## 2. Kiến trúc

```
┌──────────────────────────────────────────────────────────────┐
│                       Agent (LLM)                            │
│  "Tôi cần tạo record trong brand_identities"                │
└──────────────────────┬───────────────────────────────────────┘
                       │ tool_call: create_record(...)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    MCP Bridge (mcp_bridge.py)                 │
│                                                               │
│  @tool create_record(collection, data_json)                  │
│     │                                                         │
│     ├─ Parse data_json (str → dict if needed)                │
│     └─ execute_mcp_tool("create_record", {collection, data}) │
└──────────────────────┬───────────────────────────────────────┘
                       │ SSE Connection
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                  tmcp-m-bridge (MCP Server)                   │
│                  URL: http://localhost:7999/sse               │
│                                                               │
│  @mcp.tool() create_record(collection, data)                 │
│     └─ pb_client.create_record(collection, data)             │
└──────────────────────┬───────────────────────────────────────┘
                       │ HTTP API
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                      PocketBase                               │
│                  URL: http://localhost:8090                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. MCP Connection

### Tool Execution

```python
from mcp import ClientSession
from mcp.client.sse import sse_client

async def execute_mcp_tool(tool_name: str, arguments: dict) -> Any:
    sse_url = os.getenv("MCP_SERVER_URL", "http://localhost:7999/sse")

    async with sse_client(sse_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return result
```

### Resource Reading

```python
async def execute_mcp_read_resource(uri: str) -> Any:
    sse_url = os.getenv("MCP_SERVER_URL", "http://localhost:7999/sse")

    async with sse_client(sse_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.read_resource(uri)
            return result
```

### Connection Pattern

Mỗi tool call tạo **một SSE connection mới**:

```
Tool Call → sse_client(url) → ClientSession → initialize() → call_tool() → close
```

**Lưu ý**: Hiện tại không có connection pooling. Mỗi call tạo connection mới. Trong production có thể cần session reuse để tối ưu performance.

---

## 4. Tool Definitions

### 4.1 `list_collections`

```python
@tool
async def list_collections() -> str:
    """Lists all available collections in PocketBase."""
```

| Input    | Output                                       |
|----------|----------------------------------------------|
| *(none)* | JSON array of `{name, id, type}` objects     |

---

### 4.2 `get_collection_schema`

```python
@tool
async def get_collection_schema(collection: str) -> str:
    """Gets the schema (fields and types) for a specific collection."""
```

| Input        | Output                                               |
|--------------|------------------------------------------------------|
| `collection` | JSON array of `{name, type, required, options}`      |

---

### 4.3 `list_records`

```python
@tool
async def list_records(collection: str, page: int = 1, per_page: int = 30, filter: str = "") -> str:
    """Lists records in a collection with pagination and filtering."""
```

| Input        | Default | Mô tả                                  |
|--------------|---------|------------------------------------------|
| `collection` | *(req)* | Tên collection                          |
| `page`       | `1`     | Trang hiện tại                          |
| `per_page`   | `30`    | Số records mỗi trang                   |
| `filter`     | `""`    | PocketBase filter expression            |

---

### 4.4 `get_record`

```python
@tool
async def get_record(collection: str, record_id: str) -> str:
    """Retrieves a single record by its ID."""
```

---

### 4.5 `create_record`

```python
@tool
async def create_record(collection: str, data_json: str | dict) -> str:
    """Creates a new record in the specified collection.
    data_json must be a valid JSON string or object representing the record data."""
```

#### Data Parsing Logic

```python
if isinstance(data_json, dict):
    data = data_json                    # Dùng trực tiếp
else:
    try:
        data = json.loads(data_json)    # Parse JSON string
    except json.JSONDecodeError as e:
        return f"Error parsing data_json: {e}"
    except TypeError as e:
        return f"Error processing data_json (type {type(data_json)}): {e}"
```

**Tại sao cần dual-type input?**

LLM có thể truyền `data_json` theo 2 cách:
1. **Dict object** (khi LLM tool calling hoạt động tốt): `{"name": "EcoWare"}`
2. **JSON string** (khi LLM trả string): `'{"name": "EcoWare"}'`

Bridge xử lý cả 2 trường hợp để tăng robustness.

---

### 4.6 `update_record`

```python
@tool
async def update_record(collection: str, record_id: str, data_json: str | dict) -> str:
    """Updates an existing record.
    data_json must be a valid JSON string or object representing the data to update."""
```

Cùng logic parsing `data_json` như `create_record`.

---

### 4.7 `delete_record`

```python
@tool
async def delete_record(collection: str, record_id: str) -> str:
    """Deletes a record."""
```

---

### 4.8 `read_resource`

```python
@tool
async def read_resource(uri: str) -> str:
    """Reads a resource from the MCP server.
    Supported URIs:
    - pocketbase:// : Lists all available collections
    - pocketbase://{collection_name}/schema : Gets the schema for a collection
    - pocketbase://{collection_name}/{record_id} : Gets a specific record
    """
```

#### Supported URIs

| URI Pattern                              | Mô tả                        |
|------------------------------------------|-------------------------------|
| `pocketbase://`                          | Liệt kê tất cả collections   |
| `pocketbase://{collection}/schema`       | Lấy schema của collection     |
| `pocketbase://{collection}/{record_id}`  | Lấy record cụ thể            |

**Đây là tool quan trọng nhất** — tất cả agents đều phải gọi `read_resource("pocketbase://")` trước tiên để biết có những collections nào, sau đó check schema trước khi tạo records.

---

## 5. Tool Export

```python
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
```

`all_tools` được import bởi `nodes.py` và bind vào mỗi agent.

---

## 6. Error Handling

| Layer         | Error Type              | Xử lý                                    |
|---------------|------------------------|-------------------------------------------|
| JSON Parsing  | `JSONDecodeError`      | Trả error string cho LLM xử lý           |
| JSON Parsing  | `TypeError`            | Trả error string với type info            |
| MCP Connection| Connection refused     | Exception propagated                      |
| MCP Tool      | Tool execution error   | Error string từ MCP server                |
| Resource Read | Empty/not found        | `"Resource empty or not found."`          |
| Resource Read | Any exception          | `"Error reading resource {uri}: {e}"`     |

---

## 7. Environment Variables

| Variable         | Default                        | Mô tả                    |
|------------------|--------------------------------|---------------------------|
| `MCP_SERVER_URL` | `http://localhost:7999/sse`    | URL của MCP Bridge Server |

---

## 8. So sánh: MCP Bridge Tools vs tmcp-m-bridge Server Tools

| Feature          | MCP Bridge (`mcp_bridge.py`)      | MCP Server (`tmcp-m-bridge/tools.py`) |
|------------------|-----------------------------------|---------------------------------------|
| Framework        | LangChain `@tool`                 | MCP `@mcp.tool()`                    |
| Async            | ✅                                | ❌ (sync)                            |
| data_json parse  | ✅ (str/dict dual support)        | ❌ (dict only)                        |
| Role             | Client-side wrapper               | Server-side implementation           |
| Connection       | SSE client                        | SSE server                           |

---

## 9. Thêm Tool Mới

Để thêm tool mới vào hệ thống:

### Step 1: Thêm vào MCP Server (`tmcp-m-bridge/tools.py`)

```python
@mcp.tool()
def new_tool(param: str) -> str:
    """Description for new tool."""
    result = pb_client.some_method(param)
    return json.dumps(result, indent=2)
```

### Step 2: Wrap trong MCP Bridge (`mcp_bridge.py`)

```python
@tool
async def new_tool(param: str) -> str:
    """Description for new tool."""
    result = await execute_mcp_tool("new_tool", {"param": param})
    return result.content[0].text
```

### Step 3: Export

```python
all_tools = [
    # ... existing tools ...
    new_tool,
]
```
