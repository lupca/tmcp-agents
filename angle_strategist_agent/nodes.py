import logging
from typing import Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm_factory import get_ollama_llm
from app.services.context_fetcher import fetch_campaign_context
from app.utils.llm import parse_json_response
from app.prompts import ANGLE_STRATEGIST_PROMPT

from .state import AngleStrategistState

logger = logging.getLogger(__name__)

llm = get_ollama_llm(temperature=0.4)

async def retriever_node(state: AngleStrategistState) -> Dict[str, Any]:
    print("--- [R] Angle Strategist Retriever Node ---")

    campaign_id = state["campaign_id"]
    context, errors = await fetch_campaign_context(campaign_id)

    if errors:
        context["_errors"] = errors

    return {"context_data": context}


async def generator_node(state: AngleStrategistState) -> Dict[str, Any]:
    print("--- [G] Angle Strategist Generator Node ---")

    context = state.get("context_data", {})
    language = state.get("language", "Vietnamese")
    num_angles = state.get("num_angles", 1)
    feedback = state.get("feedback", "")

    campaign = context.get("campaign", {})
    brand = context.get("brandIdentity", {})
    persona = context.get("customerProfile", {})
    product = context.get("product", {})

    def safe_join(val):
        if isinstance(val, list):
            return ", ".join(str(v) for v in val)
        return str(val) if val else ""

    brand_voice_data = brand.get("voice_and_tone", brand.get("voiceAndTone", {}))
    brand_voice = str(brand_voice_data) if brand_voice_data else ""

    # Get strategy from kpi_targets if available
    kpi_targets = campaign.get("kpi_targets", {})
    strategy = kpi_targets.get("strategy", {}) if isinstance(kpi_targets, dict) else {}

    prompt_text = ANGLE_STRATEGIST_PROMPT.format(
        campaign_name=campaign.get("name", "Unknown Campaign"),
        campaign_goal=strategy.get("goal", campaign.get("goal", "")),
        brand_name=brand.get("brand_name", brand.get("brandName", "Brand")),
        brand_voice=brand_voice,
        brand_keywords=safe_join(brand.get("keywords", [])),
        product_name=product.get("name", "N/A"),
        product_usp=product.get("usp", "N/A"),
        product_features=safe_join(product.get("key_features", [])),
        product_benefits=safe_join(product.get("key_benefits", [])),
        persona_name=persona.get("persona_name", persona.get("personaName", "Customer")),
        persona_goals=safe_join(persona.get("goals_and_motivations", persona.get("goalsAndMotivations", []))),
        persona_pain_points=safe_join(persona.get("pain_points_and_challenges", persona.get("painPointsAndChallenges", []))),
        language=language,
        num_angles=num_angles,
        funnel_stage=state.get("funnel_stage", "Awareness"),
    )

    if feedback and "RETRY" in feedback.upper():
        prompt_text += f"\n\nPrevious feedback (please address this): {feedback}"

    response = await llm.ainvoke([
        SystemMessage(content=prompt_text),
        HumanMessage(content="Generate the angle briefs now."),
    ])

    try:
        angles = parse_json_response(response.content)
        return {"generated_angles": angles}
    except ValueError as e:
        logger.error(f"Angle strategist JSON parsing failed: {e}")
        return {"generated_angles": [{"_parse_error": True, "raw_text": response.content}]}


async def evaluator_node(state: AngleStrategistState) -> Dict[str, Any]:
    print("--- [E] Angle Strategist Evaluator Node ---")

    generated_angles = state.get("generated_angles")
    context_data = state.get("context_data", {})
    num_angles = state.get("num_angles", 1)

    if not generated_angles:
        errors = context_data.get("_errors", {})
        if errors.get("campaign"):
            return {
                "next_node": "FINISH",
                "feedback": f"CRITICAL: Campaign not found. {errors.get('campaign')}"
            }
        return {"next_node": "Generator", "feedback": "Context OK. Proceed."}

    if isinstance(generated_angles, list) and generated_angles and isinstance(generated_angles[0], dict) and generated_angles[0].get("_parse_error"):
        return {
            "next_node": "Generator",
            "feedback": "RETRY: Output was not valid JSON. Please output ONLY valid JSON.",
        }

    if not isinstance(generated_angles, list):
        return {
            "next_node": "Generator",
            "feedback": "RETRY: Output must be a JSON array of angle briefs.",
        }

    if len(generated_angles) < num_angles:
        return {
            "next_node": "Generator",
            "feedback": f"RETRY: Please generate {num_angles} distinct angle briefs.",
        }

    return {
        "next_node": "FINISH",
        "feedback": "APPROVED: Angle briefs generated.",
    }


async def saver_node(state: AngleStrategistState) -> Dict[str, Any]:
    print("--- [S] Angle Strategist Saver Node ---")
    generated_angles = state.get("generated_angles", [])
    return {
        "messages": [
            HumanMessage(content=f"Generated {len(generated_angles)} angle briefs. Ready for use.")
        ]
    }
