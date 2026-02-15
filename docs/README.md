# 📚 TMCP Marketing Agents — Documentation

> Tài liệu kiến trúc chi tiết cho hệ thống AI Multi-Agent Marketing

---

## Mục lục

| #  | Tài liệu                                                   | Mô tả                                        |
|----|-------------------------------------------------------------|-----------------------------------------------|
| 01 | [Kiến trúc Tổng quan](./01-architecture-overview.md)        | Sơ đồ hệ thống, tech stack, data flow         |
| 02 | [API Layer](./02-api-layer.md)                              | FastAPI, SSE Streaming, Endpoints              |
| 03 | [LangGraph Workflow](./03-langgraph-workflow.md)            | Graph definition, edges, routing, checkpointing|
| 04 | [Agent Nodes](./04-agent-nodes.md)                          | Supervisor, Strategist, Campaign, Research, Content |
| 05 | [MCP Bridge](./05-mcp-bridge.md)                            | Tool integration, MCP protocol, tool definitions |
| 06 | [State Management](./06-state-management.md)                | MarketingState, reducers, state flow           |
| 07 | [Prompt Engineering](./07-prompt-engineering.md)            | System prompts, patterns, collection mapping   |
| 08 | [Testing](./08-testing.md)                                  | Unit, Integration, E2E test strategy           |
| 09 | [Deployment](./09-deployment.md)                            | Docker, environment vars, production guide     |

---

## Quick Start

### Prerequisites
- Python 3.11+
- PocketBase (port 8090)
- Ollama with `qwen2.5` model (port 11434)
- tmcp-m-bridge MCP Server (port 7999)

### Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env  # Edit with your values

# 3. Start server
uvicorn app:app --reload --port 8000
```

### Test

```bash
# All tests
pytest

# By category
pytest tests/unit
pytest tests/integration
pytest tests/e2e  # requires running server
```

---

## Kiến trúc tóm tắt

```
User Request → FastAPI (SSE) → LangGraph → Supervisor → Agent Workers → MCP Bridge → PocketBase
```

### Agents

| Agent            | Vai trò                  | Output Collections                         |
|------------------|--------------------------|--------------------------------------------|
| 🎯 Supervisor    | Routing & Orchestration  | `next` (routing decision)                  |
| 📊 Strategist    | Brand & Customer Strategy| `brand_identities`, `customer_profiles`    |
| 📋 CampaignManager | Campaign Planning     | `marketing_campaigns`, `campaign_tasks`, `content_calendar_events` |
| 🔍 Researcher    | Market Research          | `content_calendar_events` (enrichment)     |
| ✍️ ContentCreator | Content Creation        | `social_posts`                             |

---

> *Generated: 2026-02-15*
