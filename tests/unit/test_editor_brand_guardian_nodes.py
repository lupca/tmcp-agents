import pytest
from unittest.mock import patch, AsyncMock
from editor_brand_guardian_agent.nodes import validator_node
from langchain_core.messages import AIMessage

@pytest.mark.asyncio
async def test_validator_node_success():
    state = {
        "brand_context": {
            "brandIdentity": {"brand_name": "Test Brand", "voice_and_tone": "Friendly"}
        },
        "master_contents": [{"id": "m1", "core_message": "Test Master"}],
        "variants": [{"id": "v1", "platform": "facebook", "adapted_copy": "Test Variant"}],
        "feedback": ""
    }

    mock_response = AIMessage(content='{"flags": [{"type": "brand_voice", "target": "master", "target_id": "m1", "message": "Too formal"}]}')

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_response

    with patch("editor_brand_guardian_agent.nodes.llm", mock_llm):
        result = await validator_node(state)

        assert "validation_results" in result
        assert "flags" in result["validation_results"]
        assert len(result["validation_results"]["flags"]) == 1
        assert result["validation_results"]["flags"][0]["type"] == "brand_voice"

@pytest.mark.asyncio
async def test_validator_node_parse_error():
    state = {
        "brand_context": {},
        "master_contents": [],
        "variants": [],
        "feedback": ""
    }

    mock_response = AIMessage(content='Invalid JSON')

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_response

    with patch("editor_brand_guardian_agent.nodes.llm", mock_llm):
        result = await validator_node(state)

        assert "validation_results" in result
        assert result["validation_results"].get("_parse_error") is True
