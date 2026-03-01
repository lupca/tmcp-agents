import json
import logging
from typing import Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm_factory import get_ollama_llm
from app.services.context_fetcher import fetch_campaign_context
from app.utils.llm import parse_json_response
from app.prompts import EDITOR_BRAND_GUARDIAN_PROMPT

from .state import EditorBrandGuardianState

logger = logging.getLogger(__name__)

llm = get_ollama_llm(temperature=0.2)

def _serialize_content(master_contents, variants):
    masters = []
    for mc in master_contents:
        masters.append({
            "id": mc.get("id"),
            "core_message": mc.get("core_message", ""),
            "extended_message": mc.get("extended_message", ""),
            "metadata": mc.get("metadata", {}),
        })
    variant_list = []
    for v in variants:
        variant_list.append({
            "id": v.get("id"),
            "platform": v.get("platform"),
            "adapted_copy": v.get("adapted_copy", ""),
            "metadata": v.get("metadata", {}),
        })
    return json.dumps({"masters": masters, "variants": variant_list})


async def retriever_node(state: EditorBrandGuardianState) -> Dict[str, Any]:
    print("--- [R] Editor Brand Guardian Retriever Node ---")

    campaign_id = state["campaign_id"]
    context, errors = await fetch_campaign_context(campaign_id)

    if errors:
        context["_errors"] = errors

    return {"brand_context": context}


async def validator_node(state: EditorBrandGuardianState) -> Dict[str, Any]:
    print("--- [G] Editor Brand Guardian Validator Node ---")

    brand = state.get("brand_context", {}).get("brandIdentity", {})
    master_contents = state.get("master_contents", [])
    variants = state.get("variants", [])

    def safe_join(val):
        if isinstance(val, list):
            return ", ".join(str(v) for v in val)
        return str(val) if val else ""

    brand_voice_data = brand.get("voice_and_tone", brand.get("voiceAndTone", {}))
    brand_voice = str(brand_voice_data) if brand_voice_data else ""

    prompt_text = EDITOR_BRAND_GUARDIAN_PROMPT.format(
        brand_name=brand.get("brand_name", brand.get("brandName", "Brand")),
        brand_voice=brand_voice,
        brand_keywords=safe_join(brand.get("keywords", [])),
    )

    payload = _serialize_content(master_contents, variants)

    response = await llm.ainvoke([
        SystemMessage(content=prompt_text),
        HumanMessage(content=f"Review this content:\n{payload}"),
    ])

    try:
        results = parse_json_response(response.content)
        return {"validation_results": results}
    except ValueError as e:
        logger.error(f"Editor guardian JSON parsing failed: {e}")
        return {"validation_results": {"_parse_error": True, "raw_text": response.content}}


async def evaluator_node(state: EditorBrandGuardianState) -> Dict[str, Any]:
    print("--- [E] Editor Brand Guardian Evaluator Node ---")

    results = state.get("validation_results")
    if not results:
        return {"next_node": "Validator", "feedback": "No validation results yet."}

    if isinstance(results, dict) and results.get("_parse_error"):
        return {
            "next_node": "Validator",
            "feedback": "RETRY: Output was not valid JSON. Please output ONLY valid JSON.",
        }

    if isinstance(results, dict) and "flags" not in results:
        return {
            "next_node": "Validator",
            "feedback": "RETRY: Missing 'flags' array in output.",
        }

    return {
        "next_node": "FINISH",
        "feedback": "APPROVED: Validation complete.",
    }


async def saver_node(state: EditorBrandGuardianState) -> Dict[str, Any]:
    print("--- [S] Editor Brand Guardian Saver Node ---")
    results = state.get("validation_results", {})
    flags = results.get("flags", []) if isinstance(results, dict) else []
    return {
        "messages": [HumanMessage(content=f"Validation complete. Flags: {len(flags)}")]
    }
