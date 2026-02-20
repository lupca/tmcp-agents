from typing import Dict, Any, List
from langchain_core.messages import HumanMessage

class StateFactory:
    @staticmethod
    def create_angle_strategist_state(campaign_id: str, workspace_id: str, language: str, num_angles: int) -> Dict[str, Any]:
        return {
            "messages": [HumanMessage(content="Generate content angles.")],
            "campaign_id": campaign_id,
            "workspace_id": workspace_id,
            "language": language,
            "num_angles": num_angles,
            "context_data": {},
            "generated_angles": None,
            "feedback": "",
            "next_node": "",
        }

    @staticmethod
    def create_master_content_state(campaign_id: str, workspace_id: str, language: str, angle: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "messages": [HumanMessage(content="Generate master content for this campaign.")],
            "campaign_id": campaign_id,
            "workspace_id": workspace_id,
            "language": language,
            "angle_context": angle,
            "context_data": {},
            "generated_content": None,
            "feedback": "",
            "next_node": "",
        }

    @staticmethod
    def create_variant_generator_state(master_id: str, platforms: List[str], workspace_id: str, language: str) -> Dict[str, Any]:
        return {
            "messages": [HumanMessage(content=f"Generate platform variants for: {', '.join(platforms)}")],
            "master_content_id": master_id,
            "platforms": platforms,
            "workspace_id": workspace_id,
            "language": language,
            "context_data": {},
            "current_platform_index": 0,
            "generated_variants": [],
            "current_variant": None,
            "feedback": "",
            "next_node": "",
        }

    @staticmethod
    def create_editor_guardian_state(campaign_id: str, workspace_id: str, language: str, master_contents: List[Dict[str, Any]], variants: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "messages": [HumanMessage(content="Validate content against brand guidelines.")],
            "campaign_id": campaign_id,
            "workspace_id": workspace_id,
            "language": language,
            "master_contents": master_contents,
            "variants": variants,
            "brand_context": {},
            "validation_results": None,
            "feedback": "",
            "next_node": "",
        }
