import asyncio
import json
import logging
import os
import uuid
import operator
from typing import Any, AsyncGenerator, Dict, List, TypedDict, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Send

from angle_strategist_agent.graph import angle_strategist_graph
from master_content_agent.graph import master_content_graph
from variant_generator_agent.graph import variant_generator_graph
from editor_brand_guardian_agent.graph import editor_brand_guardian_graph
from app.tools.mcp_bridge import execute_mcp_tool, parse_mcp_result
from app.utils.sse import sse_event
from app.utils.state_factory import StateFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VALID_PLATFORMS = ["facebook", "instagram", "linkedin", "twitter", "tiktok", "youtube", "blog", "email"]


class MasterMapState(TypedDict):
    campaign_id: str
    workspace_id: str
    language: str
    angles: List[Dict[str, Any]]
    master_results: Annotated[List[Dict[str, Any]], operator.add]


async def _create_record(collection: str, data: dict) -> dict:
    result = await execute_mcp_tool("create_record", {"collection": collection, "data": data})
    parsed, err = parse_mcp_result(result)
    if err:
        raise ValueError(err)
    return parsed or {}


async def _generate_master_for_angle(state: Dict[str, Any], semaphore: asyncio.Semaphore) -> Dict[str, Any]:
    async with semaphore:
        campaign_id = state["campaign_id"]
        workspace_id = state["workspace_id"]
        language = state.get("language", "Vietnamese")
        angle = state.get("angle", {})

        initial_state = StateFactory.create_master_content_state(
            campaign_id=campaign_id,
            workspace_id=workspace_id,
            language=language,
            angle=angle
        )

        config = {"configurable": {"thread_id": f"batch_mc_{uuid.uuid4().hex[:8]}"}}

        await master_content_graph.ainvoke(initial_state, config=config)
        final_state = await master_content_graph.aget_state(config)
        values = final_state.values
        generated_content = values.get("generated_content") or {}

        if generated_content.get("_parse_error"):
            raise ValueError("Master content generation failed with parse error")

        metadata = {
            "tone_markers": generated_content.get("tone_markers", []),
            "suggested_hashtags": generated_content.get("suggested_hashtags", []),
            "call_to_action": generated_content.get("call_to_action", ""),
            "key_benefits": generated_content.get("key_benefits", []),
            "confidence_score": generated_content.get("confidence_score", 0),
            "extended_message": generated_content.get("extended_message", ""),
            "angle": angle,
        }

        record_data = {
            "workspace_id": workspace_id,
            "campaign_id": campaign_id,
            "core_message": generated_content.get("core_message", ""),
            "approval_status": "pending",
            "primaryMediaIds": [],
            "metadata": json.dumps(metadata),
        }

        master_record = await _create_record("master_contents", record_data)
        return {
            "master_record": master_record,
            "generated_content": generated_content,
            "angle": angle,
        }


def _build_master_map_graph(semaphore: asyncio.Semaphore):
    workflow = StateGraph(MasterMapState)

    async def master_from_angle_node(state: Dict[str, Any]):
        result = await _generate_master_for_angle(state, semaphore)
        return {"master_results": [result]}

    workflow.add_node("MasterFromAngle", master_from_angle_node)

    def send_to_master_nodes(state: MasterMapState):
        return [
            Send(
                "MasterFromAngle",
                {
                    "campaign_id": state["campaign_id"],
                    "workspace_id": state["workspace_id"],
                    "language": state.get("language", "Vietnamese"),
                    "angle": angle,
                },
            )
            for angle in state.get("angles", [])
        ]

    workflow.add_conditional_edges(START, send_to_master_nodes)
    workflow.add_edge("MasterFromAngle", END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


async def _generate_variants_for_master(
    master_record: dict,
    platforms: List[str],
    workspace_id: str,
    language: str,
    semaphore: asyncio.Semaphore,
) -> List[dict]:
    async with semaphore:
        master_id = master_record.get("id")
        if not master_id:
            raise ValueError("Master record missing id")

        initial_state = StateFactory.create_variant_generator_state(
            master_id=master_id,
            platforms=platforms,
            workspace_id=workspace_id,
            language=language
        )

        config = {"configurable": {"thread_id": f"batch_var_{uuid.uuid4().hex[:8]}"}}

        await variant_generator_graph.ainvoke(initial_state, config=config)
        final_state = await variant_generator_graph.aget_state(config)
        values = final_state.values
        generated_variants = values.get("generated_variants", [])

        if not generated_variants:
            raise ValueError("Variant generation returned no variants")

        created_variants = []
        for variant in generated_variants:
            metadata = {
                "hashtags": variant.get("hashtags", []),
                "call_to_action": variant.get("callToAction", ""),
                "summary": variant.get("summary", ""),
                "character_count": variant.get("character_count", 0),
                "platform_tips": variant.get("platform_tips", ""),
                "confidence_score": variant.get("confidence_score", 0),
                "optimization_notes": variant.get("optimization_notes", ""),
                "seo_title": variant.get("seoTitle", ""),
                "seo_description": variant.get("seoDescription", ""),
                "seo_keywords": variant.get("seoKeywords", []),
            }

            record_data = {
                "workspace_id": workspace_id,
                "master_content_id": master_id,
                "platform": variant.get("_platform"),
                "adapted_copy": variant.get("adapted_copy", ""),
                "publish_status": "draft",
                "scheduled_at": None,
                "platformMediaIds": [],
                "metadata": json.dumps(metadata),
            }

            created = await _create_record("platform_variants", record_data)
            created_variants.append(created)

        return created_variants


async def batch_generate_event_stream(
    campaign_id: str,
    workspace_id: str,
    language: str,
    platforms: List[str],
    num_masters: int,
    auth_token: str = "",
) -> AsyncGenerator[str, None]:
    from app.tools.mcp_bridge import auth_token_var
    auth_token_var.set(auth_token)
    
    invalid = [p for p in platforms if p not in VALID_PLATFORMS]
    if invalid:
        yield sse_event("error", error=f"Invalid platforms: {', '.join(invalid)}")
        return

    max_concurrent = int(os.getenv("BATCH_MAX_CONCURRENT", "5"))
    semaphore = asyncio.Semaphore(max_concurrent)

    yield sse_event("status", status="active", agent="Batch", step="Generating angle briefs...")

    angle_state = StateFactory.create_angle_strategist_state(
        campaign_id=campaign_id,
        workspace_id=workspace_id,
        language=language,
        num_angles=num_masters
    )

    angle_config = {"configurable": {"thread_id": f"angles_{uuid.uuid4().hex[:8]}"}}

    try:
        await angle_strategist_graph.ainvoke(angle_state, config=angle_config)
        angle_final = await angle_strategist_graph.aget_state(angle_config)
        angles = angle_final.values.get("generated_angles", [])
        if not angles or isinstance(angles, dict):
            raise ValueError("Angle generation failed")
    except Exception as e:
        logger.error(f"Angle strategist failed: {e}")
        yield sse_event("error", error=str(e), step="Angle generation")
        return

    yield sse_event("status", status="active", agent="Batch", step=f"Generated {len(angles)} angles. Creating master posts...")

    master_graph = _build_master_map_graph(semaphore)
    master_state = {
        "campaign_id": campaign_id,
        "workspace_id": workspace_id,
        "language": language,
        "angles": angles,
        "master_results": [],
    }

    master_config = {"configurable": {"thread_id": f"master_map_{uuid.uuid4().hex[:8]}"}}

    try:
        master_results_state = await master_graph.ainvoke(master_state, config=master_config)
        master_results = master_results_state.get("master_results", [])
    except Exception as e:
        logger.error(f"Master generation failed: {e}")
        yield sse_event("error", error=str(e), step="Master generation")
        return

    yield sse_event("status", status="active", agent="Batch", step=f"Created {len(master_results)} master posts. Generating variants...")

    variant_tasks = []
    for idx, item in enumerate(master_results, start=1):
        master_record = item.get("master_record", {})
        if not master_record:
            continue
        variant_tasks.append(
            _generate_variants_for_master(master_record, platforms, workspace_id, language, semaphore)
        )
        yield sse_event("status", status="active", agent="Batch", step=f"Queued variants for master {idx}/{len(master_results)}")

    created_variants: List[dict] = []
    try:
        variant_results = await asyncio.gather(*variant_tasks)
        for created in variant_results:
            created_variants.extend(created)
    except Exception as e:
        logger.error(f"Variant generation failed: {e}")
        yield sse_event("error", error=str(e), step="Variant generation")
        return

    yield sse_event("status", status="active", agent="Batch", step="Running brand guardian checks...")

    editor_state = StateFactory.create_editor_guardian_state(
        campaign_id=campaign_id,
        workspace_id=workspace_id,
        language=language,
        master_contents=[item.get("master_record", {}) for item in master_results],
        variants=created_variants
    )

    editor_config = {"configurable": {"thread_id": f"editor_{uuid.uuid4().hex[:8]}"}}

    editor_flags = []
    try:
        await editor_brand_guardian_graph.ainvoke(editor_state, config=editor_config)
        editor_final = await editor_brand_guardian_graph.aget_state(editor_config)
        results = editor_final.values.get("validation_results", {})
        if isinstance(results, dict):
            editor_flags = results.get("flags", [])
    except Exception as e:
        logger.warning(f"Editor guardian failed: {e}")
        yield sse_event("status", status="active", agent="Batch", step="Brand guardian skipped due to error")

    yield sse_event(
        "done",
        mastersCount=len(master_results),
        variantsCount=len(created_variants),
        editorFlags=editor_flags,
    )
