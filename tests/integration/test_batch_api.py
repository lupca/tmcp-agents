import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_batch_generate_posts_endpoint():
    # Mock the batch_generate_event_stream to yield predefined SSE events
    async def mock_batch_generate_event_stream(*args, **kwargs):
        yield 'data: {"type": "status", "step": "Generating angle briefs..."}\n\n'
        yield 'data: {"type": "done", "mastersCount": 1, "variantsCount": 1, "editorFlags": []}\n\n'

    with patch("app.main.batch_generate_event_stream", side_effect=mock_batch_generate_event_stream):
        response = client.post(
            "/batch-generate-posts",
            json={
                "campaignId": "camp1",
                "workspaceId": "ws1",
                "language": "English",
                "platforms": ["facebook"],
                "numMasters": 1
            }
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        content = response.text
        assert 'data: {"type": "status", "step": "Generating angle briefs..."}' in content
        assert 'data: {"type": "done", "mastersCount": 1, "variantsCount": 1, "editorFlags": []}' in content
