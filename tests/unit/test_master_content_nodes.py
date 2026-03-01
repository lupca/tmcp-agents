"""
Unit tests for Master Content Agent nodes with auto-save disabled
"""
import pytest
from unittest.mock import patch
from master_content_agent.nodes import saver_node, evaluator_node
from master_content_agent.state import MasterContentState


class TestMasterContentSaverNode:
    """Test saver_node with auto-save disabled"""
    
    @pytest.mark.asyncio
    async def test_saver_node_returns_success_message_without_saving(self):
        """Test that saver_node returns success message without calling MCP"""
        state: MasterContentState = {
            "workspace_id": "test_ws",
            "campaign_id": "test_campaign",
            "language": "Vietnamese",
            "generated_content": {
                "core_message": "Test core message with sufficient length for validation",
                "extended_message": "Test extended message",
                "tone_markers": ["professional", "friendly"],
                "suggested_hashtags": ["#test", "#marketing"],
                "call_to_action": "Learn More",
                "confidence_score": 4.5,
            },
            "context": {},
            "messages": [],
            "next_node": None,
            "feedback": None,
            "_errors": [],
        }
        
        with patch('master_content_agent.nodes.execute_mcp_tool') as mock_mcp:
            result = await saver_node(state)
            
            # Should NOT call MCP tool
            mock_mcp.assert_not_called()
            
            # Should return success message
            assert "messages" in result
            assert len(result["messages"]) == 1
            assert "Master content generated successfully" in result["messages"][0].content
            assert "Ready for review" in result["messages"][0].content
    
    @pytest.mark.asyncio
    async def test_saver_node_handles_missing_content(self):
        """Test saver_node handles missing generated_content"""
        state: MasterContentState = {
            "workspace_id": "test_ws",
            "campaign_id": "test_campaign",
            "language": "Vietnamese",
            "generated_content": None,
            "context": {},
            "messages": [],
            "next_node": None,
            "feedback": None,
            "_errors": [],
        }
        
        result = await saver_node(state)
        
        assert "messages" in result
        assert "Nothing to save" in result["messages"][0].content
    
    @pytest.mark.asyncio
    async def test_saver_node_handles_parse_error(self):
        """Test saver_node handles content with parse error"""
        state: MasterContentState = {
            "workspace_id": "test_ws",
            "campaign_id": "test_campaign",
            "language": "Vietnamese",
            "generated_content": {
                "_parse_error": True,
                "error_message": "Invalid JSON"
            },
            "context": {},
            "messages": [],
            "next_node": None,
            "feedback": None,
            "_errors": [],
        }
        
        result = await saver_node(state)
        
        assert "messages" in result
        assert "Nothing to save" in result["messages"][0].content


class TestMasterContentEvaluatorNode:
    """Test evaluator_node with error handling"""
    
    @pytest.mark.asyncio
    async def test_evaluator_approves_valid_content(self):
        """Test evaluator approves valid content"""
        state: MasterContentState = {
            "workspace_id": "test_ws",
            "campaign_id": "test_campaign",
            "language": "Vietnamese",
            "context": {
                "campaign": {"name": "Test"},
                "brand": {"name": "Brand"},
                "persona": {"name": "Customer"}
            },
            "generated_content": {
                "core_message": "This is a test message with sufficient length for approval",
                "extended_message": "Extended message with more details",
                "confidence_score": 4.5
            },
            "messages": [],
            "next_node": None,
            "feedback": None,
            "_errors": [],
        }
        
        result = await evaluator_node(state)
        
        assert result["next_node"] == "FINISH"
        assert "APPROVED" in result["feedback"]
    
    @pytest.mark.asyncio
    async def test_evaluator_detects_context_errors(self):
        """Test evaluator detects context errors"""
        state: MasterContentState = {
            "workspace_id": "test_ws",
            "campaign_id": "test_campaign",
            "language": "Vietnamese",
            "context": {},
            "generated_content": None,
            "messages": [],
            "next_node": None,
            "feedback": None,
            "_errors": ["Campaign not found (id=test_campaign)"],
        }
        
        result = await evaluator_node(state)
        
        assert result["next_node"] == "FINISH"
        assert "CRITICAL" in result["feedback"]
        assert "Campaign not found" in result["feedback"]
