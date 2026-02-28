"""
Unit tests for Variant Generator Agent nodes with parallel execution logic
"""
import pytest
import json
from unittest.mock import AsyncMock, patch
from langchain_core.messages import AIMessage
from variant_generator_agent.nodes import saver_node, generator_node, evaluator_node
from variant_generator_agent.state import VariantGeneratorState


class TestVariantGeneratorSaverNode:
    """Test saver_node with auto-save disabled"""
    
    @pytest.mark.asyncio
    async def test_saver_node_returns_message_for_multiple_variants(self):
        """Test that saver_node returns success message for multiple platforms"""
        state: VariantGeneratorState = {
            "workspace_id": "test_ws",
            "master_content_id": "test_mc",
            "platforms": ["facebook", "instagram", "twitter"],
            "language": "Vietnamese",
            "generated_variants": [
                {
                    "_platform": "facebook",
                    "adapted_copy": "Facebook content",
                    "hashtags": ["#fb", "#social"],
                    "confidence_score": 4.5
                },
                {
                    "_platform": "instagram",
                    "adapted_copy": "Instagram content",
                    "hashtags": ["#ig", "#photo"],
                    "confidence_score": 4.3
                },
                {
                    "_platform": "twitter",
                    "adapted_copy": "Twitter content",
                    "hashtags": ["#tweet", "#news"],
                    "confidence_score": 4.6
                }
            ],
            "context_data": {},
            "messages": [],
            "current_variant": None,
            "current_platform_index": 3,
            "next_node": None,
            "feedback": None,
        }
        
        # We don't need to patch execute_mcp_tool if we don't expect it to be called
        # But if the code imports it, we might need to be careful.
        # saver_node logic currently doesn't call it if auto-save is disabled (checked code).
        
        result = await saver_node(state)
        
        assert "messages" in result
        assert len(result["messages"]) == 1
        message_content = result["messages"][0].content
        assert "3 platform variants generated successfully" in message_content
        assert "Ready for review" in message_content


class TestVariantGeneratorEvaluatorNode:
    """Test evaluator_node (Context Check Only)"""
    
    @pytest.mark.asyncio
    async def test_evaluator_approves_context_and_routes_to_generator(self):
        """Test evaluator approves context and routes to Generator"""
        state: VariantGeneratorState = {
            "workspace_id": "test_ws",
            "master_content_id": "test_mc",
            "platforms": ["facebook", "instagram"],
            "language": "Vietnamese",
            "current_variant": None,
            "current_platform_index": 0,
            "generated_variants": [],
            "context_data": {
                "masterContent": {"core_message": "Test"},
                "brandIdentity": {"name": "Test Brand"}
            },
            "messages": [],
            "next_node": None,
            "feedback": None,
        }
        
        result = await evaluator_node(state)
        
        assert result["next_node"] == "Generator"
        assert "Context OK" in result["feedback"]

    @pytest.mark.asyncio
    async def test_evaluator_detects_context_errors(self):
        """Test evaluator detects missing context"""
        state: VariantGeneratorState = {
            "workspace_id": "test_ws",
            "master_content_id": "test_mc",
            "platforms": ["facebook"],
            "language": "Vietnamese",
            "current_variant": None,
            "current_platform_index": 0,
            "generated_variants": [],
            "context_data": {
                "masterContent": {}, # Empty
                "_errors": {"masterContent": "Not found"}
            },
            "messages": [],
            "next_node": None,
            "feedback": None,
        }
        
        result = await evaluator_node(state)
        
        assert result["next_node"] == "FINISH"
        assert "CRITICAL" in result["feedback"]


class TestVariantGeneratorGeneratorNode:
    """Test generator_node with parallel execution"""

    @pytest.mark.asyncio
    async def test_generator_creates_variants_parallel(self):
        """Test that generator creates variants for all platforms"""
        state: VariantGeneratorState = {
            "workspace_id": "test_ws",
            "master_content_id": "test_mc",
            "platforms": ["facebook", "twitter"],
            "language": "English",
            "current_variant": None,
            "current_platform_index": 0,
            "generated_variants": [],
            "context_data": {
                "masterContent": {"core_message": "Buy now", "metadata": "{}"},
                "brandIdentity": {},
                "customerProfile": {}
            },
            "messages": [],
            "next_node": None,
            "feedback": None,
        }

        # Mock LLM response
        mock_response_fb = AIMessage(content=json.dumps({
            "adapted_copy": "Facebook post content here (long enough)",
            "hashtags": ["#fb"],
            "confidence_score": 0.9
        }))
        
        # We need the mock to return valid JSON for each call
        # Since it's called in parallel, side_effect might be tricky if order isn't guaranteed,
        # but for this simple test, returning a generic valid response is fine.
        
        # Actually, let's use a side_effect that checks the input prompt to customize response if needed.
        # But for now, just returning a valid JSON is enough to pass the parsing logic.

        with patch('variant_generator_agent.nodes.llm') as mock_llm:
            mock_llm.ainvoke = AsyncMock(return_value=mock_response_fb)

            result = await generator_node(state)

            # Should have generated variants for both platforms
            assert "generated_variants" in result
            variants = result["generated_variants"]
            assert len(variants) == 2

            platforms_generated = {v["_platform"] for v in variants}
            assert "facebook" in platforms_generated
            assert "twitter" in platforms_generated

            # Should have called LLM twice
            assert mock_llm.ainvoke.call_count == 2
