"""
Unit tests for Variant Generator Agent nodes with auto-save disabled
"""
import pytest
from unittest.mock import patch
from variant_generator_agent.nodes import saver_node, evaluator_node
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
            "context": {},
            "messages": [],
            "current_variant": None,
            "current_platform_index": 3,
            "next_node": None,
            "feedback": None,
            "_errors": [],
        }
        
        with patch('variant_generator_agent.nodes.execute_mcp_tool') as mock_mcp:
            result = await saver_node(state)
            
            # Should NOT call MCP tool
            mock_mcp.assert_not_called()
            
            # Should return success message with count
            assert "messages" in result
            assert len(result["messages"]) == 1
            message_content = result["messages"][0].content
            assert "3 platform variants generated successfully" in message_content
            assert "Ready for review" in message_content
    
    @pytest.mark.asyncio
    async def test_saver_node_handles_empty_variants_list(self):
        """Test saver_node with empty variants list"""
        state: VariantGeneratorState = {
            "workspace_id": "test_ws",
            "master_content_id": "test_mc",
            "platforms": ["facebook"],
            "language": "Vietnamese",
            "generated_variants": [],
            "context": {},
            "messages": [],
            "current_variant": None,
            "current_platform_index": 0,
            "next_node": None,
            "feedback": None,
            "_errors": [],
        }
        
        result = await saver_node(state)
        
        assert "messages" in result
        # Should handle gracefully even with empty list


class TestVariantGeneratorEvaluatorNode:
    """Test evaluator_node with multi-platform logic"""
    
    @pytest.mark.asyncio
    async def test_evaluator_approves_valid_variant_and_continues(self):
        """Test evaluator approves variant and moves to next platform"""
        state: VariantGeneratorState = {
            "workspace_id": "test_ws",
            "master_content_id": "test_mc",
            "platforms": ["facebook", "instagram", "twitter"],
            "language": "Vietnamese",
            "current_variant": {
                "_platform": "facebook",
                "adapted_copy": "This is valid Facebook content with sufficient length",
                "confidence_score": 4.5
            },
            "current_platform_index": 0,
            "generated_variants": [],
            "context": {
                "master_content": {"core_message": "Test"},
                "brand": {"name": "Test Brand"}
            },
            "messages": [],
            "next_node": None,
            "feedback": None,
            "_errors": [],
        }
        
        result = await evaluator_node(state)
        
        # Should approve and continue to next platform
        assert result["next_node"] == "Generator"
        assert len(result["generated_variants"]) == 1
        assert result["current_platform_index"] == 1
        assert "approved" in result["feedback"].lower()
    
    @pytest.mark.asyncio
    async def test_evaluator_finishes_after_last_platform(self):
        """Test evaluator finishes after processing all platforms"""
        state: VariantGeneratorState = {
            "workspace_id": "test_ws",
            "master_content_id": "test_mc",
            "platforms": ["facebook", "instagram"],
            "language": "Vietnamese",
            "current_variant": {
                "_platform": "instagram",
                "adapted_copy": "Valid Instagram content here with good length",
                "confidence_score": 4.3
            },
            "current_platform_index": 1,  # Last platform (index 1 of 2)
            "generated_variants": [
                {"_platform": "facebook", "adapted_copy": "FB content"}
            ],
            "context": {
                "master_content": {"core_message": "Test"},
                "brand": {"name": "Test Brand"}
            },
            "messages": [],
            "next_node": None,
            "feedback": None,
            "_errors": [],
        }
        
        result = await evaluator_node(state)
        
        # Should finish workflow
        assert result["next_node"] == "FINISH"
        assert len(result["generated_variants"]) == 2
        assert "APPROVED" in result["feedback"]
    
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
            "context": {},  # Empty context
            "messages": [],
            "next_node": None,
            "feedback": None,
            "_errors": ["Master content not found"],
        }
        
        result = await evaluator_node(state)
        
        assert result["next_node"] == "FINISH"
        assert "CRITICAL" in result["feedback"]
