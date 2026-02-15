# 🌐 API Layer — FastAPI & SSE Streaming

> **File chính:** `app.py`, `services.py`, `schemas.py`

---

## 1. Tổng quan

API Layer là tầng giao tiếp giữa frontend (tmcp-marketing-hub) và hệ thống agent. Được xây dựng bằng **FastAPI**, cung cấp:

- **REST endpoint** để nhận yêu cầu chat
- **Server-Sent Events (SSE)** để stream real-time kết quả xử lý
- **Health check** endpoint cho monitoring

---

## 2. Server Configuration

### File: `app.py`

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Marketing Agent API")

# CORS — cho phép frontend kết nối
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # ⚠️ Cần thay đổi trong production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### CORS Configuration

| Setting            | Giá trị hiện tại | Production khuyến nghị              |
|--------------------|-------------------|-------------------------------------|
| `allow_origins`    | `["*"]`           | `["https://marketing.domain.com"]`  |
| `allow_credentials`| `True`            | `True`                              |
| `allow_methods`    | `["*"]`           | `["POST", "GET"]`                   |
| `allow_headers`    | `["*"]`           | `["Content-Type", "Authorization"]` |

---

## 3. Endpoints

### 3.1 `POST /chat` — Chat với Marketing Team

**Chức năng**: Nhận tin nhắn từ user, trả về SSE stream chứa toàn bộ quá trình xử lý của agent team.

#### Request

```http
POST /chat
Content-Type: application/json

{
    "message": "Tạo chiến lược marketing cho sản phẩm EcoWare",
    "thread_id": "user_session_123"
}
```

#### Request Schema (`schemas.py`)

```python
class ChatRequest(BaseModel):
    message: str                        # Nội dung yêu cầu
    thread_id: str = "default_thread"   # Thread ID cho memory/checkpoint
```

| Field       | Type   | Required | Default            | Mô tả                              |
|-------------|--------|----------|--------------------|-------------------------------------|
| `message`   | `str`  | ✅       | —                  | Nội dung yêu cầu từ user           |
| `thread_id` | `str`  | ❌       | `"default_thread"` | ID phiên hội thoại cho checkpointing|

#### Response

**Media Type**: `text/event-stream`

Mỗi event có dạng:
```
data: {"type": "<event_type>", ...payload}\n\n
```

#### Ví dụ Response Stream

```
data: {"type": "status", "status": "active", "agent": "Supervisor"}

data: {"type": "status", "status": "thinking", "agent": "Strategist"}

data: {"type": "tool_start", "tool": "read_resource", "input": {"uri": "pocketbase://"}}

data: {"type": "tool_end", "tool": "read_resource", "output": "[\"business_ideas\", ...]"}

data: {"type": "chunk", "content": "Tôi sẽ phân tích ý tưởng..."}

data: {"type": "status", "status": "active", "agent": "Supervisor"}

data: {"type": "done"}
```

### 3.2 `GET /health` — Health Check

```http
GET /health

# Response:
{"status": "ok"}
```

---

## 4. SSE Event Generator

### File: `services.py`

Đây là core logic chuyển đổi LangGraph execution events thành SSE format.

#### Luồng xử lý

```
1. Nhận message + thread_id
2. Tạo HumanMessage → inputs
3. Gọi app_graph.astream_events() với version="v2"
4. Iterate qua mỗi event:
   - Map event_type → SSE event format
   - Yield formatted SSE data
5. Yield "done" event khi hoàn tất
6. Yield "error" event nếu có exception
```

#### Event Mapping chi tiết

```python
async for event in app_graph.astream_events(inputs, config=config, version="v2"):
    event_type = event["event"]
```

| LangGraph Event          | SSE Event Type | Payload                              | Mô tả                          |
|--------------------------|----------------|--------------------------------------|---------------------------------|
| `on_chat_model_start`    | `status`       | `{status: "thinking", agent: "..."}`| LLM bắt đầu suy nghĩ           |
| `on_tool_start`          | `tool_start`   | `{tool: "...", input: {...}}`       | Bắt đầu thực thi tool          |
| `on_tool_end`            | `tool_end`     | `{tool: "...", output: "..."}`      | Tool trả kết quả               |
| `on_chat_model_stream`   | `chunk`        | `{content: "..."}`                  | Token streaming (real-time text)|
| `on_chain_start`         | `status`       | `{status: "active", agent: "..."}`  | Node transition                 |

#### Node Filter

Chỉ emit `status.active` cho các high-level nodes:
```python
if name in ["Strategist", "Researcher", "CampaignManager", "ContentCreator", "Supervisor"]:
    yield ...
```

Điều này tránh emit quá nhiều events cho các chain nội bộ.

---

## 5. Thread ID & Memory

- `thread_id` được truyền vào config cho LangGraph checkpointer
- Cho phép **tiếp tục hội thoại** giữa các request
- Mỗi thread có memory riêng biệt (MemorySaver)

```python
config = {"configurable": {"thread_id": thread_id}}
```

**Lưu ý**: Hiện tại sử dụng `MemorySaver` (in-memory) — dữ liệu sẽ mất khi restart server. Trong production nên chuyển sang persistent checkpointer (PostgreSQL, Redis, v.v.).

---

## 6. Error Handling

```python
try:
    async for event in app_graph.astream_events(...):
        # Process events
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
except Exception as e:
    logger.error(f"Error in event generator: {e}")
    yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
```

| Tình huống                   | Xử lý                                  |
|------------------------------|-----------------------------------------|
| LLM timeout                  | Exception → SSE error event             |
| MCP Bridge connection fail   | Tool error trả về string → agent xử lý |
| JSON serialization error     | Convert to string via `str(output)`     |
| Unhandled exception          | Catch-all → SSE error event             |

---

## 7. Chạy Server

### Development
```bash
uvicorn app:app --reload --port 8000
```

### Production (Docker)
```bash
docker-compose up -d
```

### Với biến môi trường
```bash
POCKETBASE_URL=http://localhost:8090 \
OLLAMA_HOST=http://localhost:11434 \
uvicorn app:app --host 0.0.0.0 --port 8000
```

---

## 8. Sequence Diagram

```
Frontend            FastAPI            Services           LangGraph          MCP Bridge
   │                   │                  │                   │                  │
   │ POST /chat        │                  │                   │                  │
   │──────────────────►│                  │                   │                  │
   │                   │ chat_event_gen() │                   │                  │
   │                   │─────────────────►│                   │                  │
   │                   │                  │ astream_events()  │                  │
   │                   │                  │──────────────────►│                  │
   │                   │                  │                   │ Supervisor       │
   │                   │                  │◄── status event ──│                  │
   │ ◄── SSE: status ──│◄─────yield──────│                   │                  │
   │                   │                  │                   │ Strategist       │
   │                   │                  │◄── thinking ──────│                  │
   │ ◄── SSE: thinking │◄─────yield──────│                   │                  │
   │                   │                  │                   │ tool_call        │
   │                   │                  │◄── tool_start ────│─────────────────►│
   │ ◄── SSE: tool     │◄─────yield──────│                   │                  │
   │                   │                  │                   │◄─── result ──────│
   │                   │                  │◄── tool_end ──────│                  │
   │ ◄── SSE: tool_end │◄─────yield──────│                   │                  │
   │                   │                  │                   │ FINISH           │
   │                   │                  │◄── done ──────────│                  │
   │ ◄── SSE: done ────│◄─────yield──────│                   │                  │
   │                   │                  │                   │                  │
```
