
from unittest.mock import patch
from fastapi.testclient import TestClient

# Helper function to create an async generator for mocking
async def mock_event_generator(*args, **kwargs):
    yield "data: {\"type\": \"thinking\", \"content\": \"Thinking...\"}\n\n"
    yield "data: {\"type\": \"content\", \"content\": \"Hello World\"}\n\n"
    yield "data: [DONE]\n\n"

def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_chat_endpoint_validation(client: TestClient):
    # Missing 'message' field
    response = client.post("/chat", json={"thread_id": "123"})
    assert response.status_code == 422
    assert "Field required" in response.text

@patch("app.main.chat_event_generator", side_effect=mock_event_generator)
def test_chat_endpoint_success(mock_chat_gen, client: TestClient):
    response = client.post("/chat", json={"message": "Hello", "thread_id": "test_thread"})
    assert response.status_code == 200
    # iter_lines() yields text by default
    lines = list(response.iter_lines())
    # SSE format yields empty lines between data
    lines = [line for line in lines if line.strip()] 
    assert len(lines) > 0
    assert 'data: {"type": "thinking", "content": "Thinking..."}' in lines
    assert 'data: {"type": "content", "content": "Hello World"}' in lines

def test_generate_worksheet_validation(client: TestClient):
    # Invalid types
    payload = {
        "brandIds": "Not a list",
        "customerIds": "Not a list",
        "language": "Vietnamese"
    }
    response = client.post("/generate-worksheet", json=payload)
    assert response.status_code == 422

@patch("app.main.worksheet_event_generator", side_effect=mock_event_generator)
def test_generate_worksheet_success(mock_worksheet_gen, client: TestClient):
    payload = {
        "brandIds": ["123", "456"],
        "customerIds": ["789"],
        "language": "Vietnamese"
    }
    response = client.post("/generate-worksheet", json=payload)
    assert response.status_code == 200
    lines = list(response.iter_lines())
    lines = [line for line in lines if line.strip()]
    assert 'data: {"type": "thinking", "content": "Thinking..."}' in lines

@patch("app.main.brand_identity_event_generator", side_effect=mock_event_generator)
def test_generate_brand_identity_success(mock_brand_gen, client: TestClient):
    payload = {"worksheetId": "ws_123", "language": "Vietnamese"}
    response = client.post("/generate-brand-identity", json=payload)
    assert response.status_code == 200
    lines = list(response.iter_lines())
    lines = [line for line in lines if line.strip()]
    assert 'data: {"type": "thinking", "content": "Thinking..."}' in lines

@patch("app.main.customer_profile_event_generator", side_effect=mock_event_generator)
def test_generate_customer_profile_success(mock_customer_gen, client: TestClient):
    payload = {"brandIdentityId": "bi_123", "language": "English"}
    response = client.post("/generate-customer-profile", json=payload)
    assert response.status_code == 200
    lines = list(response.iter_lines())
    lines = [line for line in lines if line.strip()]
    assert 'data: {"type": "thinking", "content": "Thinking..."}' in lines

@patch("app.main.marketing_strategy_event_generator", side_effect=mock_event_generator)
def test_generate_marketing_strategy_success(mock_strategy_gen, client: TestClient):
    payload = {
        "worksheetId": "ws_123",
        "brandIdentityId": "bi_123",
        "customerProfileId": "cp_123",
        "goal": "Increase sales",
        "language": "English"
    }
    response = client.post("/generate-marketing-strategy", json=payload)
    assert response.status_code == 200
    lines = list(response.iter_lines())
    lines = [line for line in lines if line.strip()]
    assert 'data: {"type": "thinking", "content": "Thinking..."}' in lines
