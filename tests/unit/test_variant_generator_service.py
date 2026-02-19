"""
Unit tests for variant_generator service with full metadata fields
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.variant_generator import platform_variants_event_generator


class AsyncIteratorMock:
    """Helper class to mock async iterators"""
    def __init__(self, items):
        self.items = items
        self.index = 0
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


class TestVariantGeneratorService:
    """Test SSE event generation with all 12 metadata fields"""
    
    @pytest.mark.asyncio
    async def test_sse_event_returns_all_metadata_fields(self):
        """Test that final SSE event includes all metadata fields"""
        mock_state = MagicMock()
        mock_state.values = {
            "generated_variants": [
                {
                    "_platform": "facebook",
                    "adapted_copy": "Facebook post content here",
                    "hashtags": ["#ai", "#marketing"],
                    "callToAction": "Shop Now",
                    "summary": "Brief summary of the post",
                    "character_count": 150,
                    "platform_tips": "Post at 9 AM for best engagement",
                    "confidence_score": 4.5,
                    "optimization_notes": "Optimized for engagement",
                    "seoTitle": "SEO Title Here",
                    "seoDescription": "SEO description for search engines",
                    "seoKeywords": ["AI", "Marketing", "Social"],
                    "aiPrompt_used": "Generated with GPT-4",
                }
            ],
            "feedback": "All variants generated successfully",
            "messages": []
        }
        
        # Mock astream_events to return empty iterator (no events during streaming)
        mock_astream_events = AsyncIteratorMock([])
        
        with patch('app.services.variant_generator.variant_generator_graph') as mock_graph:
            # astream_events is a regular function that returns an async iterator
            mock_graph.astream_events = MagicMock(return_value=mock_astream_events)
            mock_graph.aget_state = AsyncMock(return_value=mock_state)
            
            events = []
            async for event in platform_variants_event_generator(
                master_content_id="test_mc",
                platforms=["facebook"],
                workspace_id="test_ws",
                language="Vietnamese"
            ):
                events.append(event)
            
            # Find the "done" event
            done_event = None
            for event in events:
                if '"type":"done"' in event or '"type": "done"' in event:
                    event_data = event.replace("data: ", "").strip()
                    done_event = json.loads(event_data)
                    break
            
            assert done_event is not None, f"No done event found in: {events}"
            assert done_event["type"] == "done"
            
            # Verify all metadata fields present
            variant = done_event["variants"][0]
            assert variant["platform"] == "facebook"
            assert variant["adaptedCopy"] == "Facebook post content here"
            assert variant["hashtags"] == ["#ai", "#marketing"]
            assert variant["callToAction"] == "Shop Now"
            assert variant["summary"] == "Brief summary of the post"
            assert variant["characterCount"] == 150
            assert variant["platformTips"] == "Post at 9 AM for best engagement"
            assert variant["confidenceScore"] == 4.5
            assert variant["optimizationNotes"] == "Optimized for engagement"
            assert variant["seoTitle"] == "SEO Title Here"
            assert variant["seoDescription"] == "SEO description for search engines"
            assert variant["seoKeywords"] == ["AI", "Marketing", "Social"]
    
    @pytest.mark.asyncio
    async def test_field_mapping_snake_to_camel_case(self):
        """Test snake_case to camelCase conversion"""
        mock_state = MagicMock()
        mock_state.values = {
            "generated_variants": [
                {
                    "_platform": "instagram",
                    "adapted_copy": "Content",
                    "platform_tips": "Tips here",
                    "confidence_score": 4.0,
                    "character_count": 100,
                    "hashtags": [],
                    "call_to_action": "",
                    "summary": "",
                }
            ],
            "feedback": "Success",
            "messages": []
        }
        
        mock_astream_events = AsyncIteratorMock([])
        
        with patch('app.services.variant_generator.variant_generator_graph') as mock_graph:
            mock_graph.astream_events = MagicMock(return_value=mock_astream_events)
            mock_graph.aget_state = AsyncMock(return_value=mock_state)
            
            events = []
            async for event in platform_variants_event_generator(
                master_content_id="test_mc",
                platforms=["instagram"],
                workspace_id="test_ws",
                language="English"
            ):
                events.append(event)
            
            done_event = None
            for event in events:
                if '"type":"done"' in event or '"type": "done"' in event:
                    event_data = event.replace("data: ", "").strip()
                    done_event = json.loads(event_data)
                    break
            
            variant = done_event["variants"][0]
            # Check camelCase conversion
            assert "platformTips" in variant
            assert "confidenceScore" in variant
            assert "characterCount" in variant
            assert "adaptedCopy" in variant
    
    @pytest.mark.asyncio
    async def test_missing_optional_fields_have_defaults(self):
        """Test that missing fields get default values"""
        mock_state = MagicMock()
        mock_state.values = {
            "generated_variants": [
                {
                    "_platform": "twitter",
                    "adapted_copy": "Tweet content",
                    # Missing most optional fields
                }
            ],
            "feedback": "Success",
            "messages": []
        }
        
        mock_astream_events = AsyncIteratorMock([])
        
        with patch('app.services.variant_generator.variant_generator_graph') as mock_graph:
            mock_graph.astream_events = MagicMock(return_value=mock_astream_events)
            mock_graph.aget_state = AsyncMock(return_value=mock_state)
            
            events = []
            async for event in platform_variants_event_generator(
                master_content_id="test_mc",
                platforms=["twitter"],
                workspace_id="test_ws",
                language="Vietnamese"
            ):
                events.append(event)
            
            done_event = None
            for event in events:
                if '"type":"done"' in event or '"type": "done"' in event:
                    event_data = event.replace("data: ", "").strip()
                    done_event = json.loads(event_data)
                    break
            
            variant = done_event["variants"][0]
            # Check defaults
            assert "hashtags" in variant
            assert "callToAction" in variant
            assert variant["characterCount"] == 0
            assert variant["confidenceScore"] == 0
