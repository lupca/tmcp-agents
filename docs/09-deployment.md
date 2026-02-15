# 🚀 Deployment — Docker & Infrastructure

> **Files:** `Dockerfile`, `docker-compose.yml`, `.env`

---

## 1. Tổng quan

Hệ thống được containerize bằng Docker và orchestrate qua Docker Compose. Agent service chạy trên port 8000 và kết nối đến các external services (PocketBase, Ollama, MCP Server).

---

## 2. Dockerfile

```dockerfile
# Base image
FROM python:3.11-slim

# Working directory
WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Port
EXPOSE 8000

# Default environment variables
ENV POCKETBASE_URL=http://localhost:8090
ENV OLLAMA_HOST=http://localhost:11434

# Start command
CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]
```

### Build Details

| Layer                | Mô tả                                         |
|----------------------|------------------------------------------------|
| Base image           | `python:3.11-slim` (lightweight)               |
| System deps          | `build-essential`, `curl`                      |
| Python deps          | Installed from `requirements.txt`              |
| Exposed port         | `8000`                                          |
| Default PocketBase   | `http://localhost:8090`                         |
| Default Ollama       | `http://localhost:11434`                        |

### ⚠️ Lưu ý

CMD hiện tại sử dụng `chainlit` (legacy). Trong production hiện tại nên sử dụng:

```dockerfile
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 3. Docker Compose

```yaml
version: '3.8'

services:
  agent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - POCKETBASE_URL=${POCKETBASE_URL:-http://host.docker.internal:8090}
      - OLLAMA_HOST=${OLLAMA_HOST:-http://host.docker.internal:11434}
      - POCKETBASE_USER=${POCKETBASE_USER:-admin@admin.com}
      - POCKETBASE_PASSWORD=${POCKETBASE_PASSWORD:-123qweasdzxc}
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### Network Configuration

```
┌──────────────────────────────────┐
│         Docker Container         │
│         (agent service)          │
│         Port: 8000               │
│                                  │
│  host.docker.internal ──────────►│──► Host Machine
│                                  │
└──────────────────────────────────┘
         │
    Port Mapping
         │
    Host: 8000 ←──── Container: 8000
```

`host.docker.internal` cho phép container truy cập services trên host machine (PocketBase, Ollama).

---

## 4. Environment Variables

### File: `.env`

```env
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=lsv2_pt_xxxxx
LANGSMITH_PROJECT="My First App"
GOOGLE_API_KEY=AIzaSyD_xxxxx
# OLLAMA_BASE_URL=http://172.20.10.8:11434
# OLLAMA_BASE_URL=http://localhost:11434
```

### Tất cả Environment Variables

| Variable              | Default                                | Mô tả                          | Required |
|-----------------------|----------------------------------------|---------------------------------|----------|
| `MCP_SERVER_URL`      | `http://localhost:7999/sse`            | URL MCP Bridge Server           | ✅       |
| `OLLAMA_BASE_URL`     | `http://172.20.10.8:11434`            | URL Ollama LLM server           | ✅       |
| `POCKETBASE_URL`      | `http://localhost:8090`                | URL PocketBase (Docker only)    | Docker   |
| `POCKETBASE_USER`     | `admin@admin.com`                      | PocketBase admin user           | Docker   |
| `POCKETBASE_PASSWORD` | `123qweasdzxc`                         | PocketBase admin password       | Docker   |
| `LANGSMITH_TRACING`   | `true`                                 | Enable LangSmith tracing        | ❌       |
| `LANGSMITH_ENDPOINT`  | `https://api.smith.langchain.com`      | LangSmith API URL               | ❌       |
| `LANGSMITH_API_KEY`   | *(secret)*                             | LangSmith API key               | ❌       |
| `LANGSMITH_PROJECT`   | `"My First App"`                       | LangSmith project name          | ❌       |
| `GOOGLE_API_KEY`      | *(secret)*                             | Google Gemini API key            | ❌*      |

*\* Required nếu sử dụng Gemini thay cho Ollama*

---

## 5. Dependencies (`requirements.txt`)

```
langchain                  # Core LangChain framework
langchain-community        # Community tools (DuckDuckGo)
langchain-ollama           # Ollama LLM integration
langgraph                  # Graph-based agent framework
requests                   # HTTP client

pydantic                   # Data validation
mcp                        # MCP protocol client
langchain-mcp-adapters     # LangChain ↔ MCP adapter
langchain-google-genai     # Google Gemini integration

ddgs                       # DuckDuckGo search
python-dotenv              # Environment variable loading
langsmith                  # Observability/tracing
pytest                     # Testing framework
pytest-asyncio             # Async test support
```

### Dependency Groups

| Group          | Packages                                            |
|----------------|------------------------------------------------------|
| **Core AI**    | langchain, langgraph, langchain-ollama               |
| **MCP**        | mcp, langchain-mcp-adapters                          |
| **LLM**       | langchain-ollama, langchain-google-genai              |
| **Tools**      | langchain-community, ddgs                            |
| **API**        | FastAPI, uvicorn (via langchain deps)                |
| **Infra**      | pydantic, python-dotenv, requests                    |
| **Observability** | langsmith                                         |
| **Testing**    | pytest, pytest-asyncio                               |

---

## 6. Service Dependencies

Hệ thống cần các services sau chạy trước:

```
1. PocketBase (port 8090)      ← Database
2. Ollama (port 11434)          ← LLM engine
3. tmcp-m-bridge (port 7999)    ← MCP Bridge Server
4. tmcp-agents (port 8000)      ← Agent API (this service)
```

### Startup Order

```bash
# 1. Start PocketBase
./pocketbase serve --http="0.0.0.0:8090"

# 2. Start Ollama
ollama serve

# 3. Start MCP Bridge
cd tmcp-m-bridge && python server.py

# 4. Start Agent API
cd tmcp-agents && uvicorn app:app --reload --port 8000
```

---

## 7. Production Considerations

### 7.1 Security

| Item                 | Hiện tại           | Khuyến nghị Production              |
|----------------------|--------------------|-------------------------------------|
| CORS                 | `allow_origins=*`  | Whitelist specific domains          |
| API Keys in `.env`   | Plaintext          | Sử dụng secret manager (Vault, K8s secrets) |
| PocketBase credentials | Hardcoded in compose | Environment-specific configs   |
| HTTPS                | ❌                 | TLS termination via reverse proxy   |
| Rate Limiting        | ❌                 | Implement per-user rate limits      |

### 7.2 Scalability

| Item                 | Hiện tại           | Khuyến nghị Production              |
|----------------------|--------------------|-------------------------------------|
| Memory checkpointer  | In-memory          | PostgreSQL/Redis checkpointer       |
| MCP Connection       | New per tool call  | Connection pooling                  |
| Worker processes     | Single             | Multiple uvicorn workers            |
| Load Balancing       | ❌                 | Nginx/HAProxy/K8s ingress           |

### 7.3 Monitoring

| Item                 | Hiện tại           | Khuyến nghị Production              |
|----------------------|--------------------|-------------------------------------|
| Tracing              | LangSmith          | LangSmith + custom metrics          |
| Logging              | Python logging     | Structured logging (JSON)           |
| Health check         | `GET /health`      | Thêm deep health check (DB, LLM)   |
| Metrics              | ❌                 | Prometheus + Grafana                |

---

## 8. Full Stack Docker Compose (khuyến nghị)

Để chạy toàn bộ hệ thống trong Docker:

```yaml
version: '3.8'

services:
  pocketbase:
    image: ghcr.io/muchobien/pocketbase:latest
    ports:
      - "8090:8090"
    volumes:
      - pb_data:/pb/pb_data
  
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
  
  mcp-bridge:
    build: ../tmcp-m-bridge
    ports:
      - "7999:7999"
    environment:
      - POCKETBASE_URL=http://pocketbase:8090
    depends_on:
      - pocketbase
  
  agent:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MCP_SERVER_URL=http://mcp-bridge:7999/sse
      - OLLAMA_BASE_URL=http://ollama:11434
    depends_on:
      - mcp-bridge
      - ollama

volumes:
  pb_data:
  ollama_data:
```

**Lưu ý**: Đây là template khuyến nghị, chưa được test trong production.
