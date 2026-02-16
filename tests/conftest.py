
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    """
    Create a TestClient instance for testing FastAPI endpoints.
    """
    with TestClient(app) as test_client:
        yield test_client
