import json
import logging
from typing import Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm_factory import get_ollama_llm
from app.tools.mcp_bridge import execute_mcp_tool
from app.utils.llm import parse_json_response
from app.prompts import MASTER_CONTENT_GENERATOR_PROMPT

from .state import MasterContentState

logger = logging.getLogger(__name__)

# Initialize LLM
llm = get_ollama_llm(temperature=0.7)


def _parse_mcp_result(result) -> tuple[dict | None, str | None]:
    """Parse MCP tool result. Returns (data, error_msg)."""
    text = result.content[0].text
    if text.startswith("Error:"):
        return None, text
    try:
        return json.loads(text), None
    except (json.JSONDecodeError, ValueError) as e:
        return None, f"JSON parse error: {e}. Raw: {text[:200]}"


async def retriever_node(state: MasterContentState) -> Dict[str, Any]:
    """
    Retriever (R): Gathers full context via MCP tools.
    campaign_id → campaign → worksheet, brand_identity, ideal_customer_profile
    """
    print("--- [R] Master Content Retriever Node ---")

    campaign_id = state["campaign_id"]
    context: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    # 1. Fetch Campaign
    try:
        result = await execute_mcp_tool(
            "get_record",
            {"collection": "marketing_campaigns", "record_id": campaign_id},
        )
        campaign, err = _parse_mcp_result(result)
        if campaign:
            context["campaign"] = campaign
        else:
            logger.error(f"Campaign fetch error: {err}")
            context["campaign"] = {}
            errors["campaign"] = err or "Unknown error"
    except Exception as e:
        logger.error(f"Failed to fetch campaign: {e}")
        context["campaign"] = {}
        errors["campaign"] = str(e)

    # 2. Fetch Worksheet
    worksheet_id = context.get("campaign", {}).get("worksheet_id")
    if worksheet_id:
        try:
            result = await execute_mcp_tool(
                "get_record",
                {"collection": "worksheets", "record_id": worksheet_id},
            )
            ws, err = _parse_mcp_result(result)
            context["worksheet"] = ws or {}
            if err:
                errors["worksheet"] = err
        except Exception as e:
            logger.warning(f"Failed to fetch worksheet: {e}")
            context["worksheet"] = {}
    else:
        context["worksheet"] = {}

    # 3. Fetch Brand Identity
    brand_id = context.get("campaign", {}).get("brand_id")
    if brand_id:
        try:
            result = await execute_mcp_tool(
                "get_record",
                {"collection": "brand_identities", "record_id": brand_id},
            )
            brand, err = _parse_mcp_result(result)
            context["brandIdentity"] = brand or {}
            if err:
                errors["brandIdentity"] = err
        except Exception as e:
            logger.warning(f"Failed to fetch brand identity: {e}")
            context["brandIdentity"] = {}
    else:
        context["brandIdentity"] = {}

    # 4. Fetch Customer Profile
    persona_id = context.get("campaign", {}).get("persona_id")
    if persona_id:
        try:
            result = await execute_mcp_tool(
                "get_record",
                {"collection": "ideal_customer_profiles", "record_id": persona_id},
            )
            profile, err = _parse_mcp_result(result)
            context["customerProfile"] = profile or {}
            if err:
                errors["customerProfile"] = err
        except Exception as e:
            logger.warning(f"Failed to fetch customer profile: {e}")
            context["customerProfile"] = {}
    else:
        context["customerProfile"] = {}

    # Store errors in context for the evaluator
    if errors:
        context["_errors"] = errors

    return {"context_data": context}


async def generator_node(state: MasterContentState) -> Dict[str, Any]:
    """
    Generator (G): Generates master content JSON based on the retrieved context.
    """
    print("--- [G] Master Content Generator Node ---")

    context = state.get("context_data", {})
    language = state.get("language", "Vietnamese")
    feedback = state.get("feedback", "")

    campaign = context.get("campaign", {})
    brand = context.get("brandIdentity", {})
    persona = context.get("customerProfile", {})

    # Safe extract
    def safe_join(val):
        if isinstance(val, list):
            return ", ".join(str(v) for v in val)
        return str(val) if val else ""

    brand_voice_data = brand.get("voice_and_tone", brand.get("voiceAndTone", {}))
    brand_voice = str(brand_voice_data) if brand_voice_data else ""

    prompt_text = MASTER_CONTENT_GENERATOR_PROMPT.format(
        campaign_name=campaign.get("name", "Unknown Campaign"),
        campaign_goal=campaign.get("goal", ""),
        brand_name=brand.get("brand_name", brand.get("brandName", "Brand")),
        brand_mission=brand.get("mission_statement", brand.get("missionStatement", "")),
        brand_keywords=safe_join(brand.get("keywords", [])),
        brand_voice=brand_voice,
        persona_name=persona.get("persona_name", persona.get("personaName", "Customer")),
        persona_goals=safe_join(persona.get("goals_and_motivations", persona.get("goalsAndMotivations", []))),
        persona_pain_points=safe_join(persona.get("pain_points_and_challenges", persona.get("painPointsAndChallenges", []))),
        language=language,
    )

    # If there's feedback from a previous evaluation, append it
    if feedback and "RETRY" in feedback.upper():
        prompt_text += f"\n\n**Previous feedback (please address this):** {feedback}"

    response = await llm.ainvoke([
        SystemMessage(content=prompt_text),
        HumanMessage(content="Generate the master content now."),
    ])

    # Parse the JSON from LLM response
    try:
        content_json = parse_json_response(response.content)
        return {"generated_content": content_json}
    except ValueError as e:
        logger.error(f"JSON parsing failed: {e}")
        return {"generated_content": {"raw_text": response.content, "_parse_error": True}}


async def evaluator_node(state: MasterContentState) -> Dict[str, Any]:
    """
    Evaluator (E): Evaluates the context or the generated content.
    """
    print("--- [E] Master Content Evaluator Node ---")

    generated_content = state.get("generated_content")
    context_data = state.get("context_data", {})

    # 1. Evaluate Context (if no content generated yet)
    if not generated_content:
        print("Evaluating context completeness...")
        campaign = context_data.get("campaign", {})
        retrieval_errors = context_data.get("_errors", {})
        if not campaign:
            campaign_err = retrieval_errors.get("campaign", "")
            detail = f" Detail: {campaign_err}" if campaign_err else ""
            return {
                "next_node": "FINISH",
                "feedback": f"CRITICAL: Campaign not found (id={state.get('campaign_id', '?')}). Cannot generate content without campaign context.{detail}",
            }

        # Check if we have minimum required context
        has_brand = bool(context_data.get("brandIdentity"))
        has_persona = bool(context_data.get("customerProfile"))

        if not has_brand and not has_persona:
            return {
                "next_node": "Generator",
                "feedback": "WARNING: Missing brand identity and customer profile. Content will be generic.",
            }

        return {
            "next_node": "Generator",
            "feedback": f"Context OK. Brand: {'✓' if has_brand else '✗'}, Persona: {'✓' if has_persona else '✗'}. Proceed.",
        }

    # 2. Evaluate Generated Content
    else:
        print("Evaluating generated content...")

        # Check for parse error
        if isinstance(generated_content, dict) and generated_content.get("_parse_error"):
            return {
                "next_node": "Generator",
                "feedback": "RETRY: Output was not valid JSON. Please output ONLY valid JSON.",
            }

        # Validate required fields
        required_fields = ["core_message"]
        missing = [f for f in required_fields if not generated_content.get(f)]

        if missing:
            return {
                "next_node": "Generator",
                "feedback": f"RETRY: Missing required fields: {', '.join(missing)}",
            }

        # If core_message is too short
        core_msg = generated_content.get("core_message", "")
        if len(core_msg) < 20:
            return {
                "next_node": "Generator",
                "feedback": "RETRY: core_message is too short. Provide a more detailed and compelling message.",
            }

        # All checks passed
        return {
            "next_node": "FINISH",
            "feedback": "APPROVED: Master content meets all quality criteria.",
        }


async def saver_node(state: MasterContentState) -> Dict[str, Any]:
    """
    Saver (S): Persists the approved master content to PocketBase via MCP.
    Only runs when content has been approved (after Evaluator says FINISH with generated_content).
    """
    print("--- [S] Master Content Saver Node ---")

    generated_content = state.get("generated_content")
    if not generated_content or generated_content.get("_parse_error"):
        return {"messages": [HumanMessage(content="Nothing to save — generation failed.")]}

    workspace_id = state["workspace_id"]
    campaign_id = state["campaign_id"]
    language = state.get("language", "Vietnamese")

    # Auto-save disabled - return generated content for manual review
    # record_data = {
    #     "workspace_id": workspace_id,
    #     "campaign_id": campaign_id,
    #     "core_message": generated_content.get("core_message", ""),
    #     "approval_status": "pending",
    #     "metadata": json.dumps({
    #         "tone_markers": generated_content.get("tone_markers", []),
    #         "suggested_hashtags": generated_content.get("suggested_hashtags", []),
    #         "key_benefits": generated_content.get("key_benefits", []),
    #         "call_to_action": generated_content.get("call_to_action", ""),
    #         "confidence_score": generated_content.get("confidence_score", 0),
    #         "generation_language": language,
    #     }),
    # }

    # try:
    #     result = await execute_mcp_tool(
    #         "create_record",
    #         {"collection": "master_contents", "data": record_data},
    #     )
    #     created = json.loads(result.content[0].text)
    #     record_id = created.get("id", "unknown")
    #     return {
    #         "messages": [
    #             HumanMessage(
    #                 content=f"Master content saved successfully. Record ID: {record_id}"
    #             )
    #         ]
    #     }
    # except Exception as e:
    #     logger.error(f"Failed to save master content: {e}")
    #     return {
    #         "messages": [
    #             HumanMessage(content=f"ERROR: Failed to save master content: {e}")
    #         ]
    #     }
    
    # Return generated content for manual review
    return {
        "messages": [
            HumanMessage(
                content=f"Master content generated successfully. Ready for review."
            )
        ]
    }
