import asyncio
import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm_factory import get_ollama_llm
from app.services.context_fetcher import fetch_campaign_context
from app.tools.mcp_bridge import execute_mcp_tool, parse_mcp_result
from app.utils.sse import sse_event
from app.utils.llm import parse_json_response
from app.prompts import ANGLE_STRATEGIST_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FUNNEL_STAGES = ["Awareness", "Consideration", "Conversion", "Retention"]


async def _generate_briefs_for_stage(
    stage: str,
    num_angles: int,
    context: dict,
    language: str,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Generate content briefs for a single funnel stage using the LLM."""
    async with semaphore:
        llm = get_ollama_llm(temperature=0.4)

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

        core_messaging = brand.get("core_messaging", {})
        psychographics = persona.get("psychographics", {})

        kpi_targets = campaign.get("kpi_targets", {})
        strategy = kpi_targets.get("strategy", {}) if isinstance(kpi_targets, dict) else {}

        prompt_text = ANGLE_STRATEGIST_PROMPT.format(
            campaign_name=campaign.get("name", "Unknown Campaign"),
            campaign_goal=strategy.get("goal", campaign.get("goal", "")),
            brand_name=brand.get("brand_name", brand.get("brandName", "Brand")),
            brand_voice=brand_voice,
            brand_keywords=safe_join(core_messaging.get("keywords", [])),
            product_name=product.get("name", "N/A"),
            product_usp=product.get("usp", "N/A"),
            product_features=safe_join(product.get("key_features", [])),
            product_benefits=safe_join(product.get("key_benefits", [])),
            persona_name=persona.get("persona_name", persona.get("personaName", "Customer")),
            persona_goals=safe_join(psychographics.get("goals", [])),
            persona_pain_points=safe_join(psychographics.get("pain_points", [])),
            language=language,
            num_angles=num_angles,
            funnel_stage=stage,
        )

        try:
            response = await llm.ainvoke([
                SystemMessage(content=prompt_text),
                HumanMessage(content=f"Generate {num_angles} content briefs for the {stage} funnel stage now."),
            ])

            angles = parse_json_response(response.content)

            if not isinstance(angles, list):
                return {"stage": stage, "error": "LLM output is not a list", "angles": []}

            # Ensure each angle has the correct funnel_stage
            for angle in angles:
                angle["funnel_stage"] = stage

            return {"stage": stage, "angles": angles, "error": None}

        except Exception as e:
            logger.error(f"Error generating briefs for {stage}: {e}")
            return {"stage": stage, "error": str(e), "angles": []}


async def content_briefs_event_generator(
    campaign_id: str,
    workspace_id: str,
    language: str = "Vietnamese",
    angles_per_stage: int = 6,
    auth_token: str = "",
) -> AsyncGenerator[str, None]:
    from app.tools.mcp_bridge import auth_token_var
    auth_token_var.set(auth_token)
    """
    Generate content briefs for all funnel stages in parallel.
    Uses asyncio.gather to run 4 LLM calls concurrently (one per funnel stage).
    Each call generates `angles_per_stage` distinct angle briefs.
    Results are saved to PocketBase via MCP.
    """
    try:
        # Step 1: Fetch campaign context
        yield sse_event("status", status="active", agent="ContentBriefs", step="Fetching campaign context via MCP...")
        context, errors = await fetch_campaign_context(campaign_id)

        if errors.get("campaign"):
            yield sse_event("error", error=f"Campaign fetch failed: {errors['campaign']}", step="Context retrieval")
            return

        campaign_name = context.get("campaign", {}).get("name", "Unknown")
        yield sse_event("status", status="active", agent="ContentBriefs",
                        step=f"Context loaded for campaign '{campaign_name}'. Starting parallel generation...")

        # Step 2: Run 4 parallel LLM calls (one per funnel stage)
        semaphore = asyncio.Semaphore(4)
        tasks = [
            _generate_briefs_for_stage(stage, angles_per_stage, context, language, semaphore)
            for stage in FUNNEL_STAGES
        ]

        yield sse_event("status", status="active", agent="ContentBriefs",
                        step=f"Generating {angles_per_stage} angles for each of 4 funnel stages in parallel...")

        results = await asyncio.gather(*tasks)

        # Step 3: Save all generated briefs to PocketBase
        yield sse_event("status", status="active", agent="ContentBriefs", step="Saving content briefs to database...")

        total_created = 0
        stage_errors = []

        for result in results:
            stage = result["stage"]
            if result["error"]:
                stage_errors.append(f"{stage}: {result['error']}")
                yield sse_event("status", status="warning", agent="ContentBriefs",
                                step=f"Error generating {stage}: {result['error']}")
                continue

            angles = result["angles"]
            yield sse_event("status", status="active", agent="ContentBriefs",
                            step=f"Saving {len(angles)} briefs for {stage}...")

            for angle in angles:
                try:
                    record_data = {
                        "collection": "content_briefs",
                        "data": {
                            "workspace_id": workspace_id,
                            "campaign_id": campaign_id,
                            "angle_name": angle.get("angle_name", "Untitled"),
                            "funnel_stage": stage,
                            "psychological_angle": angle.get("psychological_angle", "Logic"),
                            "pain_point_focus": angle.get("pain_point_focus", ""),
                            "key_message_variation": angle.get("key_message_variation", ""),
                            "call_to_action_direction": angle.get("call_to_action_direction", ""),
                            "brief": angle.get("brief", ""),
                        },
                    }
                    save_result = await execute_mcp_tool("create_record", record_data)
                    _, save_err = parse_mcp_result(save_result)
                    if save_err:
                        logger.warning(f"Failed to save brief: {save_err}")
                    else:
                        total_created += 1
                except Exception as e:
                    logger.warning(f"Failed to save brief for {stage}: {e}")

        # Step 4: Done
        if stage_errors:
            yield sse_event("done",
                            totalCreated=total_created,
                            totalExpected=angles_per_stage * len(FUNNEL_STAGES),
                            warnings=stage_errors)
        else:
            yield sse_event("done",
                            totalCreated=total_created,
                            totalExpected=angles_per_stage * len(FUNNEL_STAGES))

    except Exception as e:
        logger.error(f"Error in content briefs event generator: {e}")
        yield sse_event("error", error=str(e), step="Unexpected error")
