# 🧪 Testing — Chiến lược Kiểm thử

> **Thư mục:** `tests/`  
> **Config:** `pytest.ini`

---

## 1. Tổng quan

Hệ thống test chia thành 3 tầng:

```
┌─────────────────────────────────────────┐
│          E2E Tests (tests/e2e/)         │  ← Full system with API
│    Requires: running server + services  │
├─────────────────────────────────────────┤
│    Integration Tests (tests/integration/)│  ← Real components, no mocking
│    Requires: Ollama + MCP Server        │
├─────────────────────────────────────────┤
│       Unit Tests (tests/unit/)          │  ← Isolated, mocked dependencies
│    Requires: nothing (or just LLM)      │
└─────────────────────────────────────────┘
```

---

## 2. Test Configuration

### `pytest.ini`

```ini
[pytest]
asyncio_mode = auto        # Tự động xử lý async test functions
testpaths = tests           # Thư mục chứa tests
python_files = test_*.py    # Pattern file name
```

### Dependencies

```
pytest
pytest-asyncio
```

---

## 3. Unit Tests

**Thư mục:** `tests/unit/`

### Danh sách Test Files

| File                              | Mô tả                                          |
|-----------------------------------|-------------------------------------------------|
| `test_strategist_node.py`         | Test Strategist node basic execution            |
| `test_strategist_no_tools.py`     | Test khi Strategist không gọi tools             |
| `test_strategist_one_tool.py`     | Test khi Strategist gọi đúng 1 tool             |
| `test_strategist_create_record.py`| Test Strategist gọi `create_record` tool        |
| `test_strategist_json.py`         | Test JSON parsing trong tool calls              |

### Ví dụ: `test_strategist_create_record.py`

```python
from mcp_bridge import create_record

tools = [create_record]

STRATEGIST_PROMPT = "You are a strategist. Create a record in 'business_ideas' with data {'foo': 'bar'}."

from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)

async def test_strategist_create_record():
    llm_with_tools = llm.bind_tools(tools)
    messages = [
        SystemMessage(content=STRATEGIST_PROMPT),
        HumanMessage(content="Go.")
    ]
    result = await llm_with_tools.ainvoke(messages)
    print("Result:", result)
```

### Đặc điểm Unit Tests

- Sử dụng **Google Gemini** thay cho Ollama (tốc độ & độ ổn định tốt hơn cho testing)
- Focus vào **tool binding** và **LLM tool calling behavior**
- Test từng khía cạnh nhỏ: no tools, one tool, JSON format
- Không mock MCP connection (vẫn cần MCP server running)

---

## 4. Integration Tests

**Thư mục:** `tests/integration/`

### Danh sách Test Files

| File                          | Mô tả                                          |
|-------------------------------|-------------------------------------------------|
| `test_agent_basic.py`         | Test agent khởi tạo và basic invocation         |
| `test_db_connection.py`       | Test kết nối PocketBase qua MCP Bridge          |
| `test_full_integration.py`    | Full workflow test với real LLM + real DB       |
| `test_langgraph_inspection.py`| Kiểm tra graph structure (nodes, edges)         |
| `test_marketing_team_flow.py` | End-to-end marketing team flow                  |

### Ví dụ: `test_marketing_team_flow.py`

```python
from marketing_team.graph import marketing_graph

async def run_marketing_team():
    user_request = """
    I have a business idea: 'EcoWare' - sustainable, edible cutlery made from rice flour.
    Target audience: environmentally conscious millennials and event organizers.
    I need a full marketing strategy and 3 launch posts for Instagram.
    """
    
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    inputs = {"messages": [HumanMessage(content=user_request)]}
    
    async for event in marketing_graph.astream(inputs, config=config):
        for key, value in event.items():
            print(f"--- Node: {key} ---")
            if "messages" in value:
                last_msg = value["messages"][-1]
                print(f"{last_msg.name}: {last_msg.content[:200]}...")
            elif "next" in value:
                print(f"Supervisor routed to: {value['next']}")
```

### Đặc điểm Integration Tests

- Sử dụng **real LLM** (Ollama hoặc Gemini)
- Kết nối **real MCP Server** và **PocketBase**
- Test full workflow: Supervisor → Workers → Tools → Database
- Execution time có thể dài (phụ thuộc LLM response time)

---

## 5. E2E Tests

**Thư mục:** `tests/e2e/`

### Danh sách Test Files

| File                  | Mô tả                                      |
|-----------------------|---------------------------------------------|
| `test_api_stream.py`  | Test SSE streaming từ `/chat` endpoint      |

### Ví dụ: `test_api_stream.py`

```python
import httpx

async def test_streaming():
    url = "http://localhost:8000/chat"
    payload = {
        "message": "Dựa vào chiến lược marketing có id 1234 hãy viết 1 bài blog.",
        "thread_id": "demo_thread_1"
    }

    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    data = json.loads(data_str)
                    print(f"Server Event: {data}")
```

### Prerequisites

```bash
# Server phải đang chạy
uvicorn app:app --port 8000

# Sau đó chạy test
pytest tests/e2e
```

---

## 6. Chạy Tests

### Tất cả tests
```bash
pytest
```

### Theo category
```bash
pytest tests/unit
pytest tests/integration
pytest tests/e2e            # Cần server running
```

### Verbose output
```bash
pytest -v tests/unit
```

### Chạy single file
```bash
pytest tests/unit/test_strategist_node.py
```

### Chạy trực tiếp (không qua pytest)
```bash
python tests/integration/test_marketing_team_flow.py
python tests/e2e/test_api_stream.py
```

---

## 7. Infrastructure Requirements Per Test Level

| Level        | Ollama | MCP Server | PocketBase | FastAPI Server |
|-------------|--------|------------|------------|----------------|
| Unit         | ❌*    | ⚠️**       | ⚠️**       | ❌             |
| Integration  | ✅     | ✅         | ✅         | ❌             |
| E2E          | ✅     | ✅         | ✅         | ✅             |

*\* Unit tests dùng Google Gemini API thay Ollama*  
*\*\* Một số unit tests vẫn cần MCP connection cho tool testing*

---

## 8. Cải thiện tiềm năng

### Hiện tại

- Unit tests chưa hoàn toàn isolated (vẫn kết nối MCP)
- Thiếu mocking cho MCP Bridge
- Không có CI/CD pipeline defined
- Test coverage chưa đo lường

### Khuyến nghị

1. **Mock MCP Bridge** trong unit tests để đảm bảo isolation
2. **Fixtures** cho common setup (LLM, prompts, state)
3. **Test coverage reporting** (`pytest-cov`)
4. **Snapshot testing** cho prompt outputs
5. **CI/CD integration** với GitHub Actions (đã có `.github/` folder)
6. **Load testing** cho API endpoint (locust, k6)
