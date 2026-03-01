from app.utils.state_factory import StateFactory
from langchain_core.messages import HumanMessage

def test_create_angle_strategist_state():
    state = StateFactory.create_angle_strategist_state("camp1", "ws1", "English", 3)
    assert state["campaign_id"] == "camp1"
    assert state["workspace_id"] == "ws1"
    assert state["language"] == "English"
    assert state["num_angles"] == 3
    assert isinstance(state["messages"][0], HumanMessage)
    assert state["messages"][0].content == "Generate content angles."

def test_create_master_content_state():
    angle = {"angle_name": "Test Angle"}
    state = StateFactory.create_master_content_state("camp1", "ws1", "English", angle)
    assert state["campaign_id"] == "camp1"
    assert state["workspace_id"] == "ws1"
    assert state["language"] == "English"
    assert state["angle_context"] == angle
    assert isinstance(state["messages"][0], HumanMessage)
    assert state["messages"][0].content == "Generate master content for this campaign."

def test_create_variant_generator_state():
    platforms = ["facebook", "twitter"]
    state = StateFactory.create_variant_generator_state("master1", platforms, "ws1", "English")
    assert state["master_content_id"] == "master1"
    assert state["platforms"] == platforms
    assert state["workspace_id"] == "ws1"
    assert state["language"] == "English"
    assert isinstance(state["messages"][0], HumanMessage)
    assert state["messages"][0].content == "Generate platform variants for: facebook, twitter"

def test_create_editor_guardian_state():
    masters = [{"id": "m1"}]
    variants = [{"id": "v1"}]
    state = StateFactory.create_editor_guardian_state("camp1", "ws1", "English", masters, variants)
    assert state["campaign_id"] == "camp1"
    assert state["workspace_id"] == "ws1"
    assert state["language"] == "English"
    assert state["master_contents"] == masters
    assert state["variants"] == variants
    assert isinstance(state["messages"][0], HumanMessage)
    assert state["messages"][0].content == "Validate content against brand guidelines."
