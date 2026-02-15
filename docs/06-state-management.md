# 📦 State Management — MarketingState

> **File chính:** `marketing_team/state.py`

---

## 1. Tổng quan

State là cấu trúc dữ liệu chia sẻ giữa tất cả nodes trong LangGraph workflow. Mọi node đều đọc và ghi vào cùng một state object.

---

## 2. State Definition

```python
from typing import Annotated, List, TypedDict, Union
from langgraph.graph.message import add_messages

class MarketingState(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[List, add_messages]
    # The next node to route to
    next: str
```

---

## 3. State Fields

### 3.1 `messages: Annotated[List, add_messages]`

| Thuộc tính     | Giá trị                                      |
|----------------|-----------------------------------------------|
| **Type**       | `List` (danh sách LangChain messages)         |
| **Reducer**    | `add_messages` (append, không overwrite)      |
| **Mục đích**   | Lịch sử hội thoại giữa user, agents, và tools|

#### Reducer: `add_messages`

Khi một node trả về `{"messages": [new_msg]}`:
- **Không** thay thế toàn bộ messages
- **Append** message mới vào cuối danh sách
- Đảm bảo toàn bộ conversation history được giữ nguyên

```python
# Before node execution:
state["messages"] = [msg1, msg2, msg3]

# Node returns:
return {"messages": [msg4]}

# After node execution:
state["messages"] = [msg1, msg2, msg3, msg4]  # append, not replace
```

#### Message Types trong State

| Message Type     | Ý nghĩa                           | Ví dụ                                   |
|------------------|------------------------------------|-----------------------------------------|
| `HumanMessage`   | Tin nhắn từ user hoặc agent output | User request, Agent "DONE" response     |
| `AIMessage`      | Response từ LLM                    | Supervisor routing decision             |
| `SystemMessage`  | System prompt (không lưu vào state)| Agent prompts (prepend tạm thời)        |
| `ToolMessage`    | Kết quả tool execution             | PocketBase records, schema data         |

### 3.2 `next: str`

| Thuộc tính     | Giá trị                                          |
|----------------|---------------------------------------------------|
| **Type**       | `str`                                             |
| **Reducer**    | Default (overwrite)                               |
| **Mục đích**   | Chỉ định node tiếp theo trong workflow            |

#### Giá trị hợp lệ

| Value              | Routing target     |
|--------------------|---------------------|
| `"Strategist"`     | `strategist_node`   |
| `"CampaignManager"`| `campaign_manager_node` |
| `"Researcher"`     | `researcher_node`   |
| `"ContentCreator"` | `content_creator_node`  |
| `"FINISH"`         | `END` (kết thúc workflow) |

#### Ai set giá trị `next`?

Chỉ có **Supervisor** set giá trị này:

```python
def supervisor_node(state: MarketingState):
    # ...
    return {"next": "Strategist"}  # or CampaignManager, FINISH, etc.
```

Worker agents **không** set `next` — họ chỉ trả về `messages`.

---

## 4. State Flow Diagram

```
                User Request
                     │
                     ▼
        ┌──────────────────────┐
        │    Initial State     │
        │                      │
        │ messages: [          │
        │   HumanMessage(...)  │
        │ ]                    │
        │ next: (undefined)    │
        └──────────┬───────────┘
                   │ START → Supervisor
                   ▼
        ┌──────────────────────┐
        │  After Supervisor    │
        │                      │
        │ messages: [          │
        │   HumanMessage(...)  │  ← unchanged (Supervisor doesn't add messages)
        │ ]                    │
        │ next: "Strategist"   │  ← set by Supervisor
        └──────────┬───────────┘
                   │ → Strategist
                   ▼
        ┌──────────────────────┐
        │  After Strategist    │
        │                      │
        │ messages: [          │
        │   HumanMessage(...), │  ← original
        │   HumanMessage(      │  ← added by Strategist
        │     content="DONE",  │
        │     name="Strategist"│
        │   )                  │
        │ ]                    │
        │ next: "Strategist"   │  ← unchanged (Strategist doesn't set next)
        └──────────┬───────────┘
                   │ → Supervisor (fixed edge)
                   ▼
        ┌──────────────────────┐
        │  After Supervisor    │
        │                      │
        │ messages: [...]      │
        │ next: "FINISH"       │  ← Supervisor decides work is done
        └──────────┬───────────┘
                   │ → END
                   ▼
        ┌──────────────────────┐
        │     Final Result     │
        └──────────────────────┘
```

---

## 5. Checkpointing

State được tự động lưu bởi checkpointer sau mỗi node:

```
Node A executes → State saved → Node B executes → State saved → ...
```

Điều này cho phép:
- **Resume**: Tiếp tục workflow sau khi bị gián đoạn
- **Replay**: Debug bằng cách xem state tại mỗi step
- **Memory**: Cùng `thread_id` giữ nguyên conversation context

---

## 6. Lưu ý Thiết kế

### Tại sao chỉ 2 fields?

State được thiết kế **minimal** cho mô hình Supervisor:
- `messages`: Đủ để mọi agent hiểu context
- `next`: Đủ để Supervisor routing

### Mở rộng State

Nếu cần thêm thông tin chia sẻ, có thể mở rộng:

```python
class MarketingState(TypedDict):
    messages: Annotated[List, add_messages]
    next: str
    # Potential extensions:
    current_campaign_id: str          # ID chiến dịch đang xử lý
    brand_identity: dict              # Brand data để agents khỏi query lại
    error_count: int                  # Đếm lỗi để auto-retry logic
    completed_agents: List[str]       # Danh sách agents đã hoàn thành
```

### Message Growth

⚠️ **Cảnh báo**: Do reducer `add_messages` append-only, danh sách messages sẽ tăng liên tục qua mỗi node execution. Với workflow dài (nhiều agents, nhiều tool calls), messages có thể rất lớn, ảnh hưởng:
- LLM context window
- Memory usage
- Token cost

**Giải pháp tiềm năng**:
1. Message trimming (xóa messages cũ khi quá dài)
2. Message summarization (tóm tắt history)
3. Selective context (chỉ truyền messages liên quan cho mỗi agent)
