# 📐 Kiến trúc Tổng quan - TMCP Marketing Agents

> **Version:** 1.0  
> **Cập nhật:** 2026-02-15  
> **Tác giả:** Auto-generated  

---

## 1. Giới thiệu

**TMCP Marketing Agents** là hệ thống AI multi-agent được xây dựng trên nền tảng **LangGraph**, hoạt động như một đội ngũ marketing ảo tự động. Hệ thống nhận yêu cầu từ người dùng thông qua API, phân phối công việc cho các agent chuyên biệt, và tương tác trực tiếp với cơ sở dữ liệu **PocketBase** thông qua **MCP Bridge**.

### Mục tiêu

- Tự động hóa quy trình marketing từ ý tưởng đến nội dung
- Phối hợp nhiều AI agents chuyên biệt qua mô hình **Supervisor**
- Tương tác real-time với PocketBase để lưu trữ kết quả
- Cung cấp streaming response (SSE) cho frontend

---

## 2. Sơ đồ Kiến trúc Tổng thể

```
                    ┌──────────────────────────┐
                    │   tmcp-marketing-hub     │
                    │     (React Frontend)     │
                    └──────────┬───────────────┘
                               │ POST /chat (SSE)
                               ▼
                    ┌──────────────────────────┐
                    │      FastAPI Server      │
                    │        (app.py)          │
                    │   Port: 8000             │
                    └──────────┬───────────────┘
                               │
                               ▼
                    ┌──────────────────────────┐
                    │     SSE Event Service    │
                    │      (services.py)       │
                    │  astream_events v2       │
                    └──────────┬───────────────┘
                               │
                               ▼
         ┌─────────────────────────────────────────────┐
         │            LangGraph Workflow                │
         │           (marketing_team/)                  │
         │                                              │
         │    ┌─────────────┐                           │
         │    │  Supervisor │◄────────────────────┐     │
         │    └──────┬──────┘                     │     │
         │           │ (routing)                  │     │
         │    ┌──────┼──────────────┬──────────┐  │     │
         │    ▼      ▼             ▼          ▼  │     │
         │ ┌─────┐ ┌──────────┐ ┌────────┐ ┌─────────┐│
         │ │Strat│ │Campaign  │ │Research│ │Content  ││
         │ │egist│ │Manager   │ │er      │ │Creator  ││
         │ └──┬──┘ └────┬─────┘ └───┬────┘ └────┬────┘│
         │    │         │           │            │     │
         │    └─────────┴───────────┴────────────┘     │
         │                    │                         │
         └────────────────────┼─────────────────────────┘
                              │ (Tool Calls)
                              ▼
                    ┌──────────────────────────┐
                    │      MCP Bridge          │
                    │    (mcp_bridge.py)        │
                    │  LangChain Tool ↔ MCP    │
                    └──────────┬───────────────┘
                               │ SSE Connection
                               ▼
                    ┌──────────────────────────┐
                    │     tmcp-m-bridge         │
                    │   (MCP Server)            │
                    │   Port: 7999              │
                    └──────────┬───────────────┘
                               │ HTTP API
                               ▼
                    ┌──────────────────────────┐
                    │       PocketBase          │
                    │    (Database + Auth)       │
                    │   Port: 8090              │
                    └──────────────────────────┘
```

---

## 3. Luồng Dữ liệu (Data Flow)

### 3.1 Request Flow

```
1. User gửi message qua Frontend (POST /chat)
2. FastAPI nhận request, khởi tạo SSE stream
3. LangGraph bắt đầu workflow từ node START → Supervisor
4. Supervisor phân tích yêu cầu, routing đến agent phù hợp
5. Agent nhận task, gọi tools qua MCP Bridge
6. MCP Bridge kết nối đến MCP Server (tmcp-m-bridge)
7. MCP Server thực thi CRUD trên PocketBase
8. Kết quả trả về agent → agent tiếp tục hoặc trả về Supervisor
9. Supervisor quyết định bước tiếp theo hoặc FINISH
10. Mỗi bước được stream real-time qua SSE đến Frontend
```

### 3.2 SSE Event Types

| Event Type    | Mô tả                                  | Trigger                      |
|---------------|----------------------------------------|------------------------------|
| `status`      | Agent đang xử lý (thinking/active)     | `on_chat_model_start`, `on_chain_start` |
| `tool_start`  | Bắt đầu gọi tool                       | `on_tool_start`              |
| `tool_end`    | Tool trả kết quả                       | `on_tool_end`                |
| `chunk`       | Token streaming từ LLM                 | `on_chat_model_stream`       |
| `done`        | Workflow hoàn tất                       | Kết thúc vòng lặp            |
| `error`       | Lỗi xảy ra                             | Exception                    |

---

## 4. Technology Stack

| Component         | Công nghệ                   | Version   |
|-------------------|------------------------------|-----------|
| AI Framework      | LangGraph + LangChain        | Latest    |
| LLM Provider      | Ollama (qwen2.5) / Google Gemini | -     |
| API Server        | FastAPI + Uvicorn            | -         |
| Tool Protocol     | MCP (Model Context Protocol) | -         |
| Database          | PocketBase                   | -         |
| Search Engine     | DuckDuckGo (via LangChain)   | -         |
| Observability     | LangSmith                    | -         |
| Language          | Python 3.11                  | 3.11      |
| Containerization  | Docker + Docker Compose      | -         |

---

## 5. Cấu trúc Thư mục

```
tmcp-agents/
├── app.py                    # FastAPI application entry point
├── agent.py                  # Agent graph export
├── main.py                   # Standalone LangGraph test script
├── services.py               # SSE event generator service
├── schemas.py                # Pydantic request/response models
├── mcp_bridge.py             # MCP-to-LangChain tool bridge
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container build instructions
├── docker-compose.yml        # Container orchestration
├── pytest.ini                # Test configuration
├── .env                      # Environment variables
│
├── marketing_team/           # Core agent logic
│   ├── __init__.py
│   ├── graph.py              # LangGraph workflow definition
│   ├── nodes.py              # Agent node implementations
│   ├── prompts.py            # System prompts for each agent
│   └── state.py              # Shared state definition
│
├── tests/                    # Test suite
│   ├── unit/                 # Unit tests (mocked dependencies)
│   ├── integration/          # Integration tests (real components)
│   └── e2e/                  # End-to-end API tests
│
└── docs/                     # Documentation (thư mục này)
```

---

## 6. Mô hình Agent

Hệ thống sử dụng **Supervisor Pattern** — một dạng multi-agent architecture trong đó:

- **Supervisor** là node trung tâm, nhận tất cả các message và quyết định agent nào sẽ xử lý tiếp theo
- **Worker Agents** (Strategist, CampaignManager, Researcher, ContentCreator) thực hiện công việc chuyên biệt
- Mỗi worker sau khi hoàn thành sẽ trả kết quả về Supervisor
- Supervisor quyết định tiếp tục workflow hoặc kết thúc (FINISH)

### Ưu điểm của mô hình này

1. **Centralized Control**: Supervisor kiểm soát toàn bộ luồng, tránh vòng lặp vô hạn
2. **Specialization**: Mỗi agent có prompt và tools riêng biệt
3. **Scalability**: Dễ dàng thêm agent mới (chỉ cần thêm node + prompt)
4. **Observability**: Dễ debug vì mọi routing đều qua Supervisor

---

## 7. Kết nối Ngoài

### 7.1 MCP Server (tmcp-m-bridge)
- **Protocol**: SSE (Server-Sent Events)
- **URL mặc định**: `http://localhost:7999/sse`
- **Chức năng**: CRUD operations trên PocketBase

### 7.2 Ollama
- **Protocol**: HTTP REST API
- **URL mặc định**: `http://172.20.10.8:11434` (configurable)
- **Model**: `qwen2.5`

### 7.3 LangSmith (Observability)
- **Endpoint**: `https://api.smith.langchain.com`
- **Chức năng**: Tracing, monitoring agent execution
- **Config**: Qua biến môi trường `LANGSMITH_*`

### 7.4 DuckDuckGo Search
- **Sử dụng bởi**: Researcher agent
- **Thư viện**: `langchain-community` (DuckDuckGoSearchRun)
- **Không cần API key**

---

## 8. Xem thêm

- [02-api-layer.md](./02-api-layer.md) — Chi tiết FastAPI & SSE Streaming
- [03-langgraph-workflow.md](./03-langgraph-workflow.md) — LangGraph Graph Definition
- [04-agent-nodes.md](./04-agent-nodes.md) — Chi tiết từng Agent Node
- [05-mcp-bridge.md](./05-mcp-bridge.md) — MCP Bridge & Tool Integration
- [06-state-management.md](./06-state-management.md) — State & Memory
- [07-prompt-engineering.md](./07-prompt-engineering.md) — System Prompts
- [08-testing.md](./08-testing.md) — Testing Strategy
- [09-deployment.md](./09-deployment.md) — Docker & Deployment
