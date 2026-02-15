# 🤖 Agent Nodes — Chi tiết từng Agent

> **File chính:** `marketing_team/nodes.py`

---

## 1. Tổng quan

Mỗi agent node là một hàm async nhận `MarketingState` và trả về state update. Tất cả worker agents đều sử dụng chung hàm helper `run_node_agent()` để thực hiện **manual tool execution loop**.

---

## 2. LLM Configuration

```python
ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://172.20.10.8:11434")
llm = ChatOllama(model="qwen2.5", temperature=0, base_url=ollama_base_url)
```

| Parameter      | Giá trị          | Mô tả                                |
|----------------|-------------------|---------------------------------------|
| `model`        | `qwen2.5`         | Mô hình LLM từ Ollama                |
| `temperature`  | `0`               | Deterministic output (không random)    |
| `base_url`     | Từ env var        | URL của Ollama server                 |

**Lưu ý**: Trong unit tests, một số test sử dụng `ChatGoogleGenerativeAI` (Gemini) thay cho Ollama.

---

## 3. Core Helper: `run_node_agent()`

### Chức năng

Hàm trung tâm thực hiện **ReAct-style agent loop** cho tất cả worker agents:

1. Bind tools vào LLM
2. Thêm system prompt vào đầu messages
3. Lặp lại vòng: LLM suy nghĩ → gọi tool → nhận kết quả → LLM suy nghĩ lại
4. Dừng khi LLM trả lời cuối cùng (không gọi tool nữa) hoặc đạt max steps

### Signature

```python
async def run_node_agent(
    state: MarketingState,      # Current graph state
    prompt: str,                # System prompt cho agent
    name: str,                  # Tên agent (hiển thị trong messages)
    config: RunnableConfig,     # LangGraph config (thread_id, etc.)
    tools=all_tools             # Danh sách tools agent được phép dùng
) -> dict:
```

### Luồng xử lý chi tiết

```
                    ┌──────────────────┐
                    │  Bind tools to   │
                    │      LLM         │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Prepend System  │
                    │     Prompt       │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
              ┌────►│  Invoke LLM      │
              │     └────────┬─────────┘
              │              │
              │     ┌────────▼─────────┐
              │     │ Has tool_calls?  │
              │     └───┬────────┬─────┘
              │         │ Yes    │ No
              │         ▼        ▼
              │  ┌──────────┐  ┌──────────────┐
              │  │ Execute  │  │ Return final │
              │  │ ToolNode │  │   response   │
              │  └────┬─────┘  └──────────────┘
              │       │
              │  ┌────▼────────┐
              │  │ Append tool │
              │  │  results    │
              │  └────┬────────┘
              │       │
              │  ┌────▼────────┐
              │  │ step < 10?  │
              │  └──┬──────┬───┘
              │     │ Yes  │ No
              └─────┘      ▼
                    ┌──────────────────┐
                    │ Return max steps │
                    │    warning       │
                    └──────────────────┘
```

### Giới hạn

| Parameter    | Giá trị | Mô tả                                     |
|-------------|---------|---------------------------------------------|
| `max_steps` | `10`    | Tối đa 10 vòng lặp tool call               |

Khi đạt max steps mà agent chưa trả lời cuối cùng:
```python
return {
    "messages": [
        HumanMessage(
            content="Agent reached max steps without final answer.",
            name=name
        )
    ]
}
```

### Tool Execution

Sử dụng `ToolNode` từ LangGraph prebuilt:

```python
tool_executor = ToolNode(tools)
tool_output = await tool_executor.ainvoke({"messages": [result]}, config)
```

`ToolNode` tự động:
1. Parse tool calls từ LLM response
2. Gọi đúng tool function
3. Trả về `ToolMessage` với kết quả

---

## 4. Worker Agents

### 4.1 Strategist (Nhà Chiến lược)

```python
async def strategist_node(state: MarketingState, config: RunnableConfig):
    return await run_node_agent(state, STRATEGIST_PROMPT, "Strategist", config)
```

| Thuộc tính    | Giá trị                              |
|---------------|---------------------------------------|
| **Vai trò**   | Chief Marketing Strategist            |
| **Prompt**    | `STRATEGIST_PROMPT`                   |
| **Tools**     | `all_tools` (MCP Bridge tools)        |
| **Async**     | ✅                                    |
| **Output name**| `"Strategist"`                       |

#### Trách nhiệm

1. Phân tích `business_ideas` từ PocketBase
2. Tạo **Brand Identity** → lưu vào `brand_identities`
   - Name, Slogan, Mission, Color Palette, Keywords
3. Tạo **Customer Profile** → lưu vào `customer_profiles`
   - Persona Name, Demographics, Psychographics, Pain Points
4. Trả về `"DONE"` khi hoàn thành

#### Workflow bắt buộc

```
1. read_resource("pocketbase://")                       ← List collections
2. read_resource("pocketbase://brand_identities/schema") ← Check schema
3. create_record("brand_identities", data)              ← Create record
4. read_resource("pocketbase://customer_profiles/schema")← Check schema
5. create_record("customer_profiles", data)              ← Create record
```

---

### 4.2 Campaign Manager (Quản lý Chiến dịch)

```python
async def campaign_manager_node(state: MarketingState, config: RunnableConfig):
    return await run_node_agent(state, CAMPAIGN_MANAGER_PROMPT, "CampaignManager", config)
```

| Thuộc tính    | Giá trị                              |
|---------------|---------------------------------------|
| **Vai trò**   | Campaign Manager                      |
| **Prompt**    | `CAMPAIGN_MANAGER_PROMPT`             |
| **Tools**     | `all_tools` (MCP Bridge tools)        |
| **Async**     | ✅                                    |
| **Output name**| `"CampaignManager"`                  |

#### Trách nhiệm

1. Review Brand Identity và Customer Profiles đã tạo
2. Tạo **Marketing Campaign** → lưu vào `marketing_campaigns`
   - Name, Goal, Strategy, etc.
3. Chia campaign thành **Tasks** → lưu vào `campaign_tasks`
   - Task Name, Description, Status, etc.
4. Tạo **Calendar Events** → lưu vào `content_calendar_events`
5. Trả về `"DONE"` khi hoàn thành

---

### 4.3 Researcher (Nghiên cứu Thị trường)

```python
async def researcher_node(state: MarketingState, config: RunnableConfig):
    researcher_tools = all_tools + [search_tool]  # ← CÓ THÊM DuckDuckGo Search
    return await run_node_agent(state, RESEARCHER_PROMPT, "Researcher", config, tools=researcher_tools)
```

| Thuộc tính    | Giá trị                                        |
|---------------|--------------------------------------------------|
| **Vai trò**   | Market Researcher                                |
| **Prompt**    | `RESEARCHER_PROMPT`                              |
| **Tools**     | `all_tools` + `DuckDuckGoSearchRun` (**đặc biệt**)|
| **Async**     | ✅                                               |
| **Output name**| `"Researcher"`                                  |

#### Đặc biệt: DuckDuckGo Search

Researcher là **agent duy nhất** có thêm khả năng tìm kiếm web:

```python
from langchain_community.tools import DuckDuckGoSearchRun

search_tool = DuckDuckGoSearchRun()
researcher_tools = all_tools + [search_tool]
```

#### Trách nhiệm

1. Nghiên cứu trends, cultural events, holidays
2. Enrichment: thêm `aiAnalysis` và `contentSuggestion` vào `content_calendar_events`
3. Đề xuất thêm calendar events dựa trên trending topics
4. Trả về `"DONE"` khi hoàn thành

---

### 4.4 Content Creator (Sáng tạo Nội dung)

```python
async def content_creator_node(state: MarketingState, config: RunnableConfig):
    return await run_node_agent(state, CONTENT_CREATOR_PROMPT, "ContentCreator", config)
```

| Thuộc tính    | Giá trị                              |
|---------------|---------------------------------------|
| **Vai trò**   | Lead Content Creator                  |
| **Prompt**    | `CONTENT_CREATOR_PROMPT`              |
| **Tools**     | `all_tools` (MCP Bridge tools)        |
| **Async**     | ✅                                    |
| **Output name**| `"ContentCreator"`                   |

#### Trách nhiệm

1. Xem `content_calendar_events` có analysis/suggestions
2. Tạo **Social Posts** → lưu vào `social_posts`
3. Tailor content cho từng platform (LinkedIn, Facebook, Twitter)
4. Đảm bảo content engaging, on-brand, SEO-friendly
5. Trả về `"DONE"` khi hoàn thành

---

## 5. Supervisor Node

### Đặc biệt

Supervisor **KHÁC** với các worker agents:

| So sánh          | Supervisor                   | Worker Agents              |
|------------------|------------------------------|----------------------------|
| **Async**        | ❌ Synchronous               | ✅ Asynchronous            |
| **Tools**        | ❌ Không có                  | ✅ MCP Bridge + Search     |
| **Chức năng**    | Routing/Orchestration        | Task execution             |
| **Output**       | `{"next": "AgentName"}`      | `{"messages": [...]}`      |

### Implementation

```python
members = ["Strategist", "CampaignManager", "Researcher", "ContentCreator"]
system_prompt = SUPERVISOR_PROMPT.format(members=members)
options = ", ".join(members)

next_step_prompt = f"Given the conversation above, who should act next? Select one of: {options} or FINISH."

supervisor_chain = (
    ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
        ("system", next_step_prompt),
    ])
    | llm
)
```

### Routing Logic

```python
def supervisor_node(state: MarketingState):
    result = supervisor_chain.invoke(state)
    next_agent = result.content.strip()
    
    if "Strategist" in next_agent:
        return {"next": "Strategist"}
    elif "CampaignManager" in next_agent:
        return {"next": "CampaignManager"}
    elif "Researcher" in next_agent:
        return {"next": "Researcher"}
    elif "ContentCreator" in next_agent:
        return {"next": "ContentCreator"}
    else:
        return {"next": "FINISH"}
```

### Routing Principle

Supervisor tuân theo nguyên tắc **minimalistic satisfaction**:

- **Không chạy full pipeline** trừ khi user yêu cầu rõ ràng
- Khi worker trả về `"DONE"` → Supervisor kiểm tra yêu cầu gốc
- Nếu task đã hoàn thành → `FINISH`
- Nếu cần thêm → route đến agent tiếp theo

---

## 6. Bảng So sánh Agent Tools

| Agent          | MCP Tools | Search | Ghi Database | Đọc Database | Web Search |
|----------------|-----------|--------|--------------|--------------|------------|
| Supervisor     | ❌        | ❌     | ❌           | ❌           | ❌         |
| Strategist     | ✅        | ❌     | ✅           | ✅           | ❌         |
| CampaignManager| ✅        | ❌     | ✅           | ✅           | ❌         |
| Researcher     | ✅        | ✅     | ✅           | ✅           | ✅         |
| ContentCreator | ✅        | ❌     | ✅           | ✅           | ❌         |

---

## 7. Message Format

Worker agents trả về kết quả dưới dạng `HumanMessage` với `name` attribute:

```python
return {
    "messages": [
        HumanMessage(content=result.content, name=name)
    ]
}
```

**Tại sao dùng `HumanMessage` thay vì `AIMessage`?**

Trong LangGraph multi-agent, messages từ worker agents cần được Supervisor "đọc" như input. Sử dụng `HumanMessage` với `name` giúp:
1. Supervisor biết message đến từ agent nào (via `name`)
2. Tránh conflict với AIMessage của chính Supervisor
3. Maintain clean conversation flow

---

## 8. Error Handling

| Tình huống                    | Xử lý                                |
|-------------------------------|---------------------------------------|
| Tool execution fails          | Tool trả error string → LLM xử lý    |
| LLM không trả tool calls      | Trả response cuối cùng               |
| Max steps reached             | Warning message                       |
| Ollama connection error       | Exception propagated lên services.py  |
