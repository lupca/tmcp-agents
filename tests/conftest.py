
import pytest

try:
    from fastapi.testclient import TestClient
    from app.main import app
except ImportError:
    TestClient = None
    app = None

@pytest.fixture
def client():
    """
    Create a TestClient instance for testing FastAPI endpoints.
    """
    if TestClient is None:
        pytest.skip("FastAPI not installed")
    with TestClient(app) as test_client:
        yield test_client
