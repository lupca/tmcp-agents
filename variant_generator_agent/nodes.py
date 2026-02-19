import json
import logging
from typing import Dict, Any, List
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm_factory import get_ollama_llm
from app.tools.mcp_bridge import execute_mcp_tool
from app.utils.llm import parse_json_response
from app.prompts import PLATFORM_VARIANT_GENERATOR_PROMPT, PLATFORM_GUIDELINES

from .state import VariantGeneratorState

logger = logging.getLogger(__name__)

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
        mc, err = _parse_mcp_result(result)
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

    # 2. Fetch Campaign
    campaign_id = context.get("masterContent", {}).get("campaign_id")
    if campaign_id:
        try:
            result = await execute_mcp_tool(
                "get_record",
                {"collection": "marketing_campaigns", "record_id": campaign_id},
            )
            data, err = _parse_mcp_result(result)
            context["campaign"] = data or {}
            if err:
                errors["campaign"] = err
        except Exception as e:
            logger.warning(f"Failed to fetch campaign: {e}")
            context["campaign"] = {}
    else:
        context["campaign"] = {}

    # 3. Fetch Brand Identity
    brand_id = context.get("campaign", {}).get("brand_id")
    if brand_id:
        try:
            result = await execute_mcp_tool(
                "get_record",
                {"collection": "brand_identities", "record_id": brand_id},
            )
            data, err = _parse_mcp_result(result)
            context["brandIdentity"] = data or {}
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
            data, err = _parse_mcp_result(result)
            context["customerProfile"] = data or {}
            if err:
                errors["customerProfile"] = err
        except Exception as e:
            logger.warning(f"Failed to fetch customer profile: {e}")
            context["customerProfile"] = {}
    else:
        context["customerProfile"] = {}

    if errors:
        context["_errors"] = errors

    return {
        "context_data": context,
        "current_platform_index": 0,
        "generated_variants": [],
    }


async def generator_node(state: VariantGeneratorState) -> Dict[str, Any]:
    """
    Generator (G): Generates a variant for the current platform.
    Processes one platform at a time; the graph loops back for the next.
    """
    platforms = state.get("platforms", [])
    idx = state.get("current_platform_index", 0)
    platform = platforms[idx]

    print(f"--- [G] Variant Generator Node — Platform: {platform} ---")

    context = state.get("context_data", {})
    language = state.get("language", "Vietnamese")
    feedback = state.get("feedback", "")

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
    extended_message = mc.get("extended_message", "")
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

    prompt_text = PLATFORM_VARIANT_GENERATOR_PROMPT.format(
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

    if feedback and "RETRY" in feedback.upper():
        prompt_text += f"\n\n**Previous feedback (please address this):** {feedback}"

    response = await llm.ainvoke([
        SystemMessage(content=prompt_text),
        HumanMessage(content=f"Generate the {platform} variant now."),
    ])

    try:
        variant_json = parse_json_response(response.content)
        variant_json["_platform"] = platform
        return {"current_variant": variant_json}
    except ValueError as e:
        logger.error(f"JSON parsing failed for {platform}: {e}")
        return {
            "current_variant": {
                "raw_text": response.content,
                "_parse_error": True,
                "_platform": platform,
            }
        }


async def evaluator_node(state: VariantGeneratorState) -> Dict[str, Any]:
    """
    Evaluator (E): Evaluates context or a generated variant.
    Routes to Generator, NextPlatform, or FINISH.
    """
    print("--- [E] Variant Evaluator Node ---")

    current_variant = state.get("current_variant")
    context_data = state.get("context_data", {})
    platforms = state.get("platforms", [])
    idx = state.get("current_platform_index", 0)

    # 1. Context evaluation (before any generation)
    if current_variant is None:
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

    # 2. Evaluate the generated variant
    if isinstance(current_variant, dict) and current_variant.get("_parse_error"):
        return {
            "next_node": "Generator",
            "feedback": "RETRY: Output was not valid JSON. Please output ONLY valid JSON.",
        }

    adapted_copy = current_variant.get("adapted_copy", "")
    if not adapted_copy or len(adapted_copy) < 10:
        return {
            "next_node": "Generator",
            "feedback": "RETRY: adapted_copy is missing or too short. Provide more content.",
        }

    # Variant is OK — accumulate and move to next platform
    accumulated = list(state.get("generated_variants", []))
    accumulated.append(current_variant)
    next_idx = idx + 1

    if next_idx < len(platforms):
        return {
            "generated_variants": accumulated,
            "current_variant": None,
            "current_platform_index": next_idx,
            "next_node": "Generator",
            "feedback": f"Platform '{current_variant.get('_platform')}' approved. Moving to next platform.",
        }
    else:
        # All platforms done
        return {
            "generated_variants": accumulated,
            "current_variant": None,
            "next_node": "FINISH",
            "feedback": "APPROVED: All platform variants generated successfully.",
        }


async def saver_node(state: VariantGeneratorState) -> Dict[str, Any]:
    """
    Saver (S): Persists all approved variants to PocketBase via MCP.
    """
    print("--- [S] Variant Saver Node ---")

    generated_variants = state.get("generated_variants", [])
    if not generated_variants:
        return {"messages": [HumanMessage(content="Nothing to save — no variants generated.")]}

    workspace_id = state["workspace_id"]
    master_content_id = state["master_content_id"]
    language = state.get("language", "Vietnamese")

    # Inherit media from master content
    mc = state.get("context_data", {}).get("masterContent", {})
    media_ids = mc.get("primaryMediaIds", [])
    if isinstance(media_ids, str):
        try:
            media_ids = json.loads(media_ids) if media_ids else []
        except (json.JSONDecodeError, TypeError):
            media_ids = []

    created_ids = []

    for variant in generated_variants:
        platform = variant.get("_platform", "unknown")
        record_data = {
            "workspace_id": workspace_id,
            "master_content_id": master_content_id,
            "platform": platform,
            "adapted_copy": variant.get("adapted_copy", ""),
            "platformMediaIds": media_ids,
            "publish_status": "draft",
            "metadata": json.dumps({
                "seoTitle": variant.get("seoTitle", ""),
                "seoDescription": variant.get("seoDescription", ""),
                "seoKeywords": variant.get("seoKeywords", []),
                "hashtags": variant.get("hashtags", []),
                "summary": variant.get("summary", ""),
                "callToAction": variant.get("callToAction", ""),
                "platform_tips": variant.get("platform_tips", ""),
                "aiPrompt_used": variant.get("aiPrompt_used", ""),
                "confidence_score": variant.get("confidence_score", 0),
                "character_count": variant.get("character_count", 0),
                "optimization_notes": variant.get("optimization_notes", ""),
                "generated_at": datetime.now().isoformat(),
                "generation_language": language,
            }),
        }

        # Auto-save disabled - skip database persistence
        # try:
        #     result = await execute_mcp_tool(
        #         "create_record",
        #         {"collection": "platform_variants", "data": record_data},
        #     )
        #     created = json.loads(result.content[0].text)
        #     created_ids.append({"platform": platform, "id": created.get("id")})
        # except Exception as e:
        #     logger.error(f"Failed to save {platform} variant: {e}")
        #     return {
        #         "messages": [
        #             HumanMessage(
        #                 content=f"ERROR: Failed to save {platform} variant: {e}. Aborting."
        #             )
        #         ]
        #     }

    # Return generated variants for manual review
    # summary = ", ".join(f"{v['platform']}={v['id']}" for v in created_ids)
    return {
        "messages": [
            HumanMessage(
                content=f"All {len(generated_variants)} platform variants generated successfully. Ready for review."
            )
        ]
    }
