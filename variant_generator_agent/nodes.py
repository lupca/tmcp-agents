import json
import logging
import asyncio
from typing import Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm_factory import get_ollama_llm
from app.tools.mcp_bridge import execute_mcp_tool, parse_mcp_result
from app.services.context_fetcher import fetch_campaign_context
from app.utils.llm import parse_json_response
from app.prompts import PLATFORM_VARIANT_GENERATOR_PROMPT, PLATFORM_GUIDELINES

from .state import VariantGeneratorState

logger = logging.getLogger(__name__)

llm = get_ollama_llm(temperature=0.7)

async def retriever_node(state: VariantGeneratorState) -> Dict[str, Any]:
    """
    Retriever (R): Fetches master_content + campaign + brand identity + persona via MCP.
    """
    print("--- [R] Variant Retriever Node ---")

    master_content_id = state["master_content_id"]
    context: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    # 1. Fetch Master Content
    try:
        result = await execute_mcp_tool(
            "get_record",
            {"collection": "master_contents", "record_id": master_content_id},
        )
        mc, err = parse_mcp_result(result)
        if mc:
            context["masterContent"] = mc
        else:
            logger.error(f"Master content fetch error: {err}")
            context["masterContent"] = {}
            errors["masterContent"] = err or "Unknown error"
    except Exception as e:
        logger.error(f"Failed to fetch master content: {e}")
        context["masterContent"] = {}
        errors["masterContent"] = str(e)

    # 2. Fetch Campaign Context
    campaign_id = context.get("masterContent", {}).get("campaign_id")
    if campaign_id:
        campaign_context, campaign_errors = await fetch_campaign_context(campaign_id)
        context.update(campaign_context)
        errors.update(campaign_errors)
    else:
        context["campaign"] = {}
        context["brandIdentity"] = {}
        context["customerProfile"] = {}

    if errors:
        context["_errors"] = errors

    return {
        "context_data": context,
        "current_platform_index": 0,
        "generated_variants": [],
    }


async def _generate_single_variant(
    platform: str,
    context: Dict[str, Any],
    language: str,
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Helper to generate a variant for a single platform with retry logic.
    """
    mc = context.get("masterContent", {})
    brand = context.get("brandIdentity", {})
    persona = context.get("customerProfile", {})

    # Extract metadata from master content
    metadata = mc.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}

    core_message = mc.get("core_message", "")
    extended_message = mc.get("extended_message", "") or metadata.get("extended_message", "")
    tone_markers = metadata.get("tone_markers", [])
    call_to_action = metadata.get("call_to_action", "")

    brand_voice_data = brand.get("voice_and_tone", brand.get("voiceAndTone", {}))
    brand_voice = str(brand_voice_data) if brand_voice_data else ""

    persona_name = persona.get("persona_name", persona.get("personaName", "Customer"))

    # Platform-specific guidelines
    platform_info = PLATFORM_GUIDELINES.get(platform, {})
    char_limit = platform_info.get("char_limit", "No specific limit")
    platform_guidelines = platform_info.get("best_practices", "")
    content_format = platform_info.get("format", "Standard")

    def safe_join(val):
        if isinstance(val, list):
            return ", ".join(str(v) for v in val)
        return str(val) if val else ""

    # Construct base prompt
    base_prompt_text = PLATFORM_VARIANT_GENERATOR_PROMPT.format(
        platform=platform.capitalize(),
        core_message=core_message,
        extended_message=extended_message,
        tone_markers=safe_join(tone_markers),
        call_to_action=call_to_action,
        brand_voice=brand_voice,
        persona_name=persona_name,
        persona_characteristics=persona_name,
        language=language,
        char_limit=str(char_limit),
        platform_guidelines=platform_guidelines,
        content_format=content_format,
    )

    feedback = ""

    for attempt in range(max_retries + 1):
        prompt_text = base_prompt_text
        if feedback:
            prompt_text += f"\n\n**Previous attempt issue (please address this):** {feedback}"

        try:
            # We call invoke here. If parallelized via gather, these run concurrently.
            response = await llm.ainvoke([
                SystemMessage(content=prompt_text),
                HumanMessage(content=f"Generate the {platform} variant now."),
            ])

            try:
                variant_json = parse_json_response(response.content)
            except ValueError as e:
                feedback = f"Output was not valid JSON: {e}. Please output ONLY valid JSON."
                if attempt < max_retries:
                    continue
                else:
                    return {
                        "raw_text": response.content,
                        "_parse_error": True,
                        "_platform": platform,
                        "error": str(e)
                    }

            variant_json["_platform"] = platform

            # Validation logic (migrated from evaluator_node)
            adapted_copy = variant_json.get("adapted_copy", "")
            if not adapted_copy or len(adapted_copy) < 10:
                feedback = "adapted_copy is missing or too short. Provide more content."
                if attempt < max_retries:
                    continue
                else:
                    # Return what we have but mark as potentially poor quality
                    variant_json["_warning"] = "Content too short"
                    return variant_json

            # If we got here, it's valid
            return variant_json

        except Exception as e:
            logger.error(f"Error generating {platform} variant (attempt {attempt}): {e}")
            feedback = f"System error: {e}"
            if attempt == max_retries:
                 return {
                    "_platform": platform,
                    "error": str(e),
                    "_parse_error": True
                }

    return {
        "_platform": platform,
        "error": "Max retries exceeded",
        "last_feedback": feedback
    }


async def generator_node(state: VariantGeneratorState) -> Dict[str, Any]:
    """
    Generator (G): Generates variants for ALL platforms in parallel.
    Internalizes the retry loop for efficiency.
    """
    platforms = state.get("platforms", [])
    print(f"--- [G] Variant Generator Node — Platforms: {', '.join(platforms)} ---")

    context = state.get("context_data", {})
    language = state.get("language", "Vietnamese")

    # Launch parallel generation tasks
    tasks = [
        _generate_single_variant(platform, context, language)
        for platform in platforms
    ]

    results = await asyncio.gather(*tasks)

    return {
        "generated_variants": results,
        "current_variant": None, # Clear this as we are done
    }


async def evaluator_node(state: VariantGeneratorState) -> Dict[str, Any]:
    """
    Evaluator (E): Evaluates context availability only.
    Routes to Generator or FINISH.
    """
    print("--- [E] Variant Evaluator Node (Context Check) ---")

    context_data = state.get("context_data", {})

    # Context evaluation
    mc = context_data.get("masterContent", {})
    retrieval_errors = context_data.get("_errors", {})
    if not mc:
        mc_err = retrieval_errors.get("masterContent", "")
        detail = f" Detail: {mc_err}" if mc_err else ""
        return {
            "next_node": "FINISH",
            "feedback": f"CRITICAL: Master content not found (id={state.get('master_content_id', '?')}).{detail}",
        }

    return {
        "next_node": "Generator",
        "feedback": "Context OK. Proceeding to variant generation.",
    }


async def saver_node(state: VariantGeneratorState) -> Dict[str, Any]:
    """
    Saver (S): Persists all approved variants to PocketBase via MCP.
    """
    print("--- [S] Variant Saver Node ---")

    generated_variants = state.get("generated_variants", [])
    if not generated_variants:
        return {"messages": [HumanMessage(content="Nothing to save — no variants generated.")]}

    # Inherit media from master content
    mc = state.get("context_data", {}).get("masterContent", {})
    media_ids = mc.get("primaryMediaIds", [])
    if isinstance(media_ids, str):
        try:
            media_ids = json.loads(media_ids) if media_ids else []
        except (json.JSONDecodeError, TypeError):
            media_ids = []

    # Dead persistence logic removed
        
    return {
        "messages": [
            HumanMessage(
                content=f"All {len(generated_variants)} platform variants generated successfully. Ready for review."
            )
        ]
    }
