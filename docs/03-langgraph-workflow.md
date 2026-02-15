# 🔄 LangGraph Workflow — Graph Definition

> **File chính:** `marketing_team/graph.py`

---

## 1. Tổng quan

LangGraph workflow là "trái tim" của hệ thống agent. Nó định nghĩa:

- **Nodes**: Các agent tham gia workflow
- **Edges**: Luồng di chuyển giữa các nodes
- **Conditional Routing**: Logic để Supervisor điều phối agents
- **Checkpointing**: Lưu trạng thái cho memory

---

## 2. Graph Definition

### Source Code

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import MarketingState
from .nodes import (
    supervisor_node,
    strategist_node,
    campaign_manager_node,
    researcher_node,
    content_creator_node
)

# 1. Create the graph
workflow = StateGraph(MarketingState)

# 2. Add nodes
workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("Strategist", strategist_node)
workflow.add_node("CampaignManager", campaign_manager_node)
workflow.add_node("Researcher", researcher_node)
workflow.add_node("ContentCreator", content_creator_node)

# 3. Add edges
workflow.add_edge(START, "Supervisor")

# Conditional routing from Supervisor
workflow.add_conditional_edges(
    "Supervisor",
    lambda state: state["next"],
    {
        "Strategist": "Strategist",
        "CampaignManager": "CampaignManager",
        "Researcher": "Researcher",
        "ContentCreator": "ContentCreator",
        "FINISH": END
    }
)

# All workers return to Supervisor
workflow.add_edge("Strategist", "Supervisor")
workflow.add_edge("CampaignManager", "Supervisor")
workflow.add_edge("Researcher", "Supervisor")
workflow.add_edge("ContentCreator", "Supervisor")

# 4. Compile with memory
memory = MemorySaver()
marketing_graph = workflow.compile(checkpointer=memory)
```

---

## 3. Sơ đồ Graph

```
                        ┌──────────┐
                        │  START   │
                        └────┬─────┘
                             │
                             ▼
                    ┌────────────────┐
              ┌────►│   Supervisor   │◄────────────────────────────┐
              │     └───────┬────────┘                             │
              │             │                                      │
              │             │ conditional_edges                    │
              │             │ (based on state["next"])             │
              │             │                                      │
              │    ┌────────┼──────────┬──────────┐                │
              │    ▼        ▼          ▼          ▼                │
              │ ┌──────┐ ┌────────┐ ┌────────┐ ┌────────────┐     │
              │ │Strat-│ │Campaign│ │Research│ │  Content   │     │
              │ │egist │ │Manager │ │  er    │ │  Creator   │     │
              │ └──┬───┘ └───┬────┘ └───┬────┘ └─────┬──────┘     │
              │    │         │          │             │            │
              │    └─────────┴──────────┴─────────────┘            │
              │              │                                     │
              └──────────────┘                                     │
                                                                   │
                             │ (if next == "FINISH")               │
                             ▼                                     │
                        ┌──────────┐                               │
                        │   END    │                               │
                        └──────────┘
```

---

## 4. Chi tiết Các Node

| Node Name          | Function              | Async | Has Tools | Mô tả                                |
|--------------------|-----------------------|-------|-----------|---------------------------------------|
| `Supervisor`       | `supervisor_node()`   | ❌    | ❌        | Routing agent — quyết định bước tiếp  |
| `Strategist`       | `strategist_node()`   | ✅    | ✅ MCP    | Xây dựng chiến lược marketing         |
| `CampaignManager`  | `campaign_manager_node()` | ✅ | ✅ MCP    | Quản lý chiến dịch & tasks            |
| `Researcher`       | `researcher_node()`   | ✅    | ✅ MCP + Search | Nghiên cứu thị trường            |
| `ContentCreator`   | `content_creator_node()` | ✅  | ✅ MCP    | Tạo nội dung social media             |

---

## 5. Edge Types

### 5.1 Fixed Edges (cố định)

```python
workflow.add_edge(START, "Supervisor")         # Luôn bắt đầu từ Supervisor
workflow.add_edge("Strategist", "Supervisor")  # Workers luôn quay về Supervisor
workflow.add_edge("CampaignManager", "Supervisor")
workflow.add_edge("Researcher", "Supervisor")
workflow.add_edge("ContentCreator", "Supervisor")
```

**Pattern**: `START → Supervisor → Worker → Supervisor → Worker → ... → END`

### 5.2 Conditional Edges (có điều kiện)

```python
workflow.add_conditional_edges(
    "Supervisor",                    # Source node
    lambda state: state["next"],     # Routing function
    {                                # Routing map
        "Strategist": "Strategist",
        "CampaignManager": "CampaignManager",
        "Researcher": "Researcher",
        "ContentCreator": "ContentCreator",
        "FINISH": END
    }
)
```

**Routing function**: Đọc `state["next"]` — giá trị được set bởi `supervisor_node()`.

---

## 6. Checkpointing & Memory

### MemorySaver

```python
memory = MemorySaver()
marketing_graph = workflow.compile(checkpointer=memory)
```

- **Loại**: In-memory checkpoint
- **Chức năng**: Lưu trạng thái graph sau mỗi node execution
- **Phạm vi**: Mỗi `thread_id` có state riêng biệt
- **Persistence**: ❌ Mất khi restart server

### Sử dụng trong config

```python
config = {"configurable": {"thread_id": "user_thread_123"}}
result = await marketing_graph.astream_events(inputs, config=config)
```

### Lưu ý Production

Trong production, nên thay `MemorySaver` bằng persistent checkpointer:

| Checkpointer          | Use Case                      |
|------------------------|-------------------------------|
| `MemorySaver`          | Development, testing          |
| `SqliteSaver`          | Single-server production      |
| `PostgresSaver`        | Multi-server, scalable        |
| `RedisSaver`           | High-performance caching      |

---

## 7. Graph Compilation

```python
marketing_graph = workflow.compile(checkpointer=memory)
```

Compile tạo ra một **CompiledGraph** object có các methods:

| Method              | Mô tả                                    | Sử dụng trong          |
|---------------------|-------------------------------------------|-------------------------|
| `invoke()`          | Chạy đồng bộ, trả full result            | Testing                 |
| `ainvoke()`         | Chạy bất đồng bộ                         | Testing async           |
| `astream()`         | Stream node outputs                       | Integration tests       |
| `astream_events()`  | Stream chi tiết mọi event (LLM, tools)   | Production (services.py)|

---

## 8. Execution Flow Example

### Yêu cầu: "Tạo chiến lược marketing cho EcoWare"

```
Step 1: START → Supervisor
        Supervisor phân tích: "Đây là yêu cầu chiến lược"
        state["next"] = "Strategist"

Step 2: Supervisor → Strategist
        Strategist:
          - Gọi read_resource("pocketbase://") 
          - Gọi read_resource("pocketbase://brand_identities/schema")
          - Gọi create_record("brand_identities", {...})
          - Gọi create_record("customer_profiles", {...})
          - Trả về "DONE"
        
Step 3: Strategist → Supervisor
        Supervisor phân tích: "Strategist đã DONE, user chỉ yêu cầu chiến lược"
        state["next"] = "FINISH"

Step 4: Supervisor → END
```

### Yêu cầu: "Tạo full marketing plan và 3 bài social media"

```
Step 1: START → Supervisor → Strategist (chiến lược + brand)
Step 2: Strategist → Supervisor → CampaignManager (tạo campaign + tasks)  
Step 3: CampaignManager → Supervisor → Researcher (nghiên cứu thị trường)
Step 4: Researcher → Supervisor → ContentCreator (tạo 3 bài social)
Step 5: ContentCreator → Supervisor → FINISH
```

---

## 9. Export

```python
# agent.py
from marketing_team.graph import marketing_graph as app_graph
```

`app_graph` được import bởi `services.py` để sử dụng trong SSE event generator.
