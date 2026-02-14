# Tests

This directory contains the test suite for the TMCP Agents project.

## Structure

- **unit/**: Unit tests for individual components (nodes, tools). Use mocking where possible.
- **integration/**: Integration tests checking the interaction between components (graph, db).
- **e2e/**: End-to-end tests validating the API and full system behavior.

## Running Tests

Prerequisites:
```bash
pip install -r requirements.txt
```

Run all tests:
```bash
pytest
```

Run specific categories:
```bash
pytest tests/unit
pytest tests/integration
```

**Note:** E2E tests (`tests/e2e`) require the API server to be running:
```bash
uvicorn app:app --port 8000
```
Then runs:
```bash
pytest tests/e2e
```
