import pytest
from unittest.mock import patch, AsyncMock
from angle_strategist_agent.nodes import generator_node, evaluator_node
from langchain_core.messages import AIMessage

@pytest.mark.asyncio
async def test_generator_node_success():
    state = {
        "context_data": {
            "campaign": {"name": "Test Campaign", "goal": "Test Goal"},
            "brandIdentity": {"brand_name": "Test Brand", "voice_and_tone": "Friendly"},
            "customerProfile": {"persona_name": "Test Persona"}
        },
        "language": "English",
        "num_angles": 2,
        "feedback": ""
    }

    mock_response = AIMessage(content='[{"angle_name": "Angle 1"}, {"angle_name": "Angle 2"}]')

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_response

    with patch("angle_strategist_agent.nodes.llm", mock_llm):
        result = await generator_node(state)

        assert "generated_angles" in result
        assert len(result["generated_angles"]) == 2
        assert result["generated_angles"][0]["angle_name"] == "Angle 1"

@pytest.mark.asyncio
async def test_generator_node_parse_error():
    state = {
        "context_data": {},
        "language": "English",
        "num_angles": 1,
        "feedback": ""
    }

    mock_response = AIMessage(content='Invalid JSON')

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_response

    with patch("angle_strategist_agent.nodes.llm", mock_llm):
        result = await generator_node(state)

        assert "generated_angles" in result
        assert len(result["generated_angles"]) == 1
        assert result["generated_angles"][0].get("_parse_error") is True

@pytest.mark.asyncio
async def test_evaluator_node_success():
    state = {
        "generated_angles": [{"angle_name": "Angle 1"}, {"angle_name": "Angle 2"}],
        "num_angles": 2,
        "context_data": {}
    }

    result = await evaluator_node(state)
    assert result["next_node"] == "FINISH"
    assert "APPROVED" in result["feedback"]

@pytest.mark.asyncio
async def test_evaluator_node_not_enough_angles():
    state = {
        "generated_angles": [{"angle_name": "Angle 1"}],
        "num_angles": 2,
        "context_data": {}
    }

    result = await evaluator_node(state)
    assert result["next_node"] == "Generator"
    assert "RETRY" in result["feedback"]

@pytest.mark.asyncio
async def test_evaluator_node_parse_error():
    state = {
        "generated_angles": [{"_parse_error": True}],
        "num_angles": 1,
        "context_data": {}
    }

    result = await evaluator_node(state)
    assert result["next_node"] == "Generator"
    assert "RETRY" in result["feedback"]
