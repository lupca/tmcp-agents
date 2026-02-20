import logging
from typing import Dict, Any, Tuple

from app.tools.mcp_bridge import execute_mcp_tool, parse_mcp_result

logger = logging.getLogger(__name__)

async def fetch_campaign_context(campaign_id: str) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Fetches the full context for a campaign including:
    - Campaign details
    - Worksheet
    - Brand Identity
    - Ideal Customer Profile
    
    Returns:
        Tuple of (context_data, errors)
    """
    context: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    # 1. Fetch Campaign
    try:
        result = await execute_mcp_tool(
            "get_record",
            {"collection": "marketing_campaigns", "record_id": campaign_id},
        )
        campaign, err = parse_mcp_result(result)
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
            ws, err = parse_mcp_result(result)
            context["worksheet"] = ws or {}
            if err:
                errors["worksheet"] = err
        except Exception as e:
            logger.warning(f"Failed to fetch worksheet: {e}")
            context["worksheet"] = {}
            errors["worksheet"] = str(e)
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
            brand, err = parse_mcp_result(result)
            context["brandIdentity"] = brand or {}
            if err:
                errors["brandIdentity"] = err
        except Exception as e:
            logger.warning(f"Failed to fetch brand identity: {e}")
            context["brandIdentity"] = {}
            errors["brandIdentity"] = str(e)
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
            profile, err = parse_mcp_result(result)
            context["customerProfile"] = profile or {}
            if err:
                errors["customerProfile"] = err
        except Exception as e:
            logger.warning(f"Failed to fetch customer profile: {e}")
            context["customerProfile"] = {}
            errors["customerProfile"] = str(e)
    else:
        context["customerProfile"] = {}

    return context, errors
