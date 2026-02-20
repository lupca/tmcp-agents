import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.batch_generator import batch_generate_event_stream, _generate_master_for_angle, _generate_variants_for_master

@pytest.mark.asyncio
async def test_batch_generate_event_stream_invalid_platforms():
    events = []
    async for event in batch_generate_event_stream("camp1", "ws1", "English", ["invalid_platform"], 1):
        events.append(event)

    assert len(events) == 1
    assert "error" in events[0]
    assert "Invalid platforms" in events[0]

@pytest.mark.asyncio
async def test_batch_generate_event_stream_success():
    # Mock the graphs
    async def mock_angle_ainvoke(*args, **kwargs):
        pass
    
    async def mock_angle_aget_state(*args, **kwargs):
        class MockState:
            def __init__(self):
                self.values = {"generated_angles": [{"angle_name": "Angle 1"}]}
        return MockState()

    async def mock_master_ainvoke(*args, **kwargs):
        return {"master_results": [{"master_record": {"id": "m1"}, "generated_content": {}, "angle": {}}]}

    async def mock_variant_gather(*args, **kwargs):
        return [[{"id": "v1", "platform": "facebook"}]]

    async def mock_editor_ainvoke(*args, **kwargs):
        pass

    async def mock_editor_aget_state(*args, **kwargs):
        class MockState:
            def __init__(self):
                self.values = {"validation_results": {"flags": []}}
        return MockState()

    with patch("app.services.batch_generator.angle_strategist_graph.ainvoke", new_callable=AsyncMock, side_effect=mock_angle_ainvoke), \
         patch("app.services.batch_generator.angle_strategist_graph.aget_state", new_callable=AsyncMock, side_effect=mock_angle_aget_state), \
         patch("app.services.batch_generator._build_master_map_graph") as mock_build_master, \
         patch("app.services.batch_generator._generate_variants_for_master", new_callable=AsyncMock) as mock_gen_variants, \
         patch("app.services.batch_generator.editor_brand_guardian_graph.ainvoke", new_callable=AsyncMock, side_effect=mock_editor_ainvoke), \
         patch("app.services.batch_generator.editor_brand_guardian_graph.aget_state", new_callable=AsyncMock, side_effect=mock_editor_aget_state):
        
        mock_master_graph = MagicMock()
        mock_master_graph.ainvoke = AsyncMock(side_effect=mock_master_ainvoke)
        mock_build_master.return_value = mock_master_graph

        mock_gen_variants.return_value = [{"id": "v1", "platform": "facebook"}]

        events = []
        async for event in batch_generate_event_stream("camp1", "ws1", "English", ["facebook"], 1):
            events.append(event)

        # Verify events
        assert any("Generating angle briefs" in e for e in events)
        assert any("Generated 1 angles" in e for e in events)
        assert any("Created 1 master posts" in e for e in events)
        assert any("Running brand guardian checks" in e for e in events)
        assert any("done" in e for e in events)

@pytest.mark.asyncio
async def test_generate_master_for_angle_success():
    semaphore = asyncio.Semaphore(1)
    state = {"campaign_id": "camp1", "workspace_id": "ws1", "language": "English", "angle": {"angle_name": "A1"}}

    async def mock_ainvoke(*args, **kwargs):
        pass

    async def mock_aget_state(*args, **kwargs):
        class MockState:
            def __init__(self):
                self.values = {"generated_content": {"core_message": "Test"}}
        return MockState()

    async def mock_create_record(*args, **kwargs):
        return {"id": "m1"}

    with patch("app.services.batch_generator.master_content_graph.ainvoke", new_callable=AsyncMock, side_effect=mock_ainvoke), \
         patch("app.services.batch_generator.master_content_graph.aget_state", new_callable=AsyncMock, side_effect=mock_aget_state), \
         patch("app.services.batch_generator._create_record", new_callable=AsyncMock, side_effect=mock_create_record):
        
        result = await _generate_master_for_angle(state, semaphore)
        assert result["master_record"]["id"] == "m1"
        assert result["generated_content"]["core_message"] == "Test"
        assert result["angle"]["angle_name"] == "A1"

@pytest.mark.asyncio
async def test_generate_variants_for_master_success():
    semaphore = asyncio.Semaphore(1)
    master_record = {"id": "m1"}
    platforms = ["facebook"]

    async def mock_ainvoke(*args, **kwargs):
        pass

    async def mock_aget_state(*args, **kwargs):
        class MockState:
            def __init__(self):
                self.values = {"generated_variants": [{"_platform": "facebook", "adapted_copy": "Test"}]}
        return MockState()

    async def mock_create_record(*args, **kwargs):
        return {"id": "v1", "platform": "facebook"}

    with patch("app.services.batch_generator.variant_generator_graph.ainvoke", new_callable=AsyncMock, side_effect=mock_ainvoke), \
         patch("app.services.batch_generator.variant_generator_graph.aget_state", new_callable=AsyncMock, side_effect=mock_aget_state), \
         patch("app.services.batch_generator._create_record", new_callable=AsyncMock, side_effect=mock_create_record):
        
        result = await _generate_variants_for_master(master_record, platforms, "ws1", "English", semaphore)
        assert len(result) == 1
        assert result[0]["id"] == "v1"
