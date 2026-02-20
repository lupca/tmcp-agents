import logging
from typing import Dict, Any, Tuple

from app.tools.mcp_bridge import execute_mcp_tool, parse_mcp_result

logger = logging.getLogger(__name__)

async def fetch_campaign_context(campaign_id: str) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Fetches the full context for a campaign including:
    - Campaign details
    - Product (via product_id on campaign)
    - Brand Identity (via product_id.brand_id or worksheet.brandRefs)
    - Worksheet (via worksheet_id on campaign)
    - Ideal Customer Profile (via worksheet.customerRefs)
    
    Returns:
        Tuple of (context_data, errors)
    """
    context: Dict[str, Any] = {}
    errors: Dict[str, str] = {}

    # 1. Fetch Campaign with expand to get product->brand chain
    try:
        result = await execute_mcp_tool(
            "get_record",
            {
                "collection": "marketing_campaigns",
                "record_id": campaign_id,
                "expand": "product_id,product_id.brand_id,worksheet_id",
            },
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

    campaign_data = context.get("campaign", {})
    expand = campaign_data.get("expand", {})

    # 2. Extract Worksheet from expand or fetch separately
    worksheet_data = expand.get("worksheet_id")
    if worksheet_data:
        context["worksheet"] = worksheet_data
    else:
        worksheet_id = campaign_data.get("worksheet_id")
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

    # 3. Extract Product from expand
    product_data = expand.get("product_id")
    if product_data:
        context["product"] = product_data
    else:
        product_id = campaign_data.get("product_id")
        if product_id:
            try:
                result = await execute_mcp_tool(
                    "get_record",
                    {
                        "collection": "products_services",
                        "record_id": product_id,
                        "expand": "brand_id",
                    },
                )
                prod, err = parse_mcp_result(result)
                context["product"] = prod or {}
                if err:
                    errors["product"] = err
            except Exception as e:
                logger.warning(f"Failed to fetch product: {e}")
                context["product"] = {}
                errors["product"] = str(e)
        else:
            context["product"] = {}

    # 4. Extract Brand Identity: prefer product->brand expand, fallback to worksheet.brandRefs
    brand_data = None
    # Try product.expand.brand_id first
    product = context.get("product", {})
    if product:
        brand_data = product.get("expand", {}).get("brand_id")
    # Also try campaign.expand.product_id.expand.brand_id
    if not brand_data and expand.get("product_id"):
        brand_data = expand["product_id"].get("expand", {}).get("brand_id")

    if brand_data:
        context["brandIdentity"] = brand_data
    else:
        # Fallback: fetch first brandRef from worksheet
        worksheet = context.get("worksheet", {})
        brand_refs = worksheet.get("brandRefs", [])
        if brand_refs and len(brand_refs) > 0:
            try:
                result = await execute_mcp_tool(
                    "get_record",
                    {"collection": "brand_identities", "record_id": brand_refs[0]},
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

    # 5. Fetch Customer Profile from worksheet.customerRefs
    worksheet = context.get("worksheet", {})
    customer_refs = worksheet.get("customerRefs", [])
    if customer_refs and len(customer_refs) > 0:
        try:
            result = await execute_mcp_tool(
                "get_record",
                {"collection": "customer_personas", "record_id": customer_refs[0]},
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
