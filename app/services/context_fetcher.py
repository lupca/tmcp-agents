import asyncio
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

    # 2 & 3. Fetch Worksheet and Product in Phase 1
    async def _fetch_worksheet():
        worksheet_data = expand.get("worksheet_id")
        if worksheet_data:
            return worksheet_data, None

        worksheet_id = campaign_data.get("worksheet_id")
        if not worksheet_id:
            return {}, None

        try:
            result = await execute_mcp_tool(
                "get_record",
                {"collection": "worksheets", "record_id": worksheet_id},
            )
            ws, err = parse_mcp_result(result)
            return ws or {}, err
        except Exception as e:
            logger.warning(f"Failed to fetch worksheet: {e}")
            return {}, str(e)

    async def _fetch_product():
        product_data = expand.get("product_id")
        if product_data:
            return product_data, None

        product_id = campaign_data.get("product_id")
        if not product_id:
            return {}, None

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
            return prod or {}, err
        except Exception as e:
            logger.warning(f"Failed to fetch product: {e}")
            return {}, str(e)

    # Execute Phase 1 fetches in parallel
    worksheet_task = asyncio.create_task(_fetch_worksheet())
    product_task = asyncio.create_task(_fetch_product())

    (ws_res, ws_err), (prod_res, prod_err) = await asyncio.gather(worksheet_task, product_task)

    context["worksheet"] = ws_res
    if ws_err: errors["worksheet"] = ws_err

    context["product"] = prod_res
    if prod_err: errors["product"] = prod_err

    # 4 & 5. Fetch Brand Identity and Customer Profile in Phase 2
    async def _fetch_brand():
        brand_data = None
        # Try product.expand.brand_id first
        product = context.get("product", {})
        if product:
            brand_data = product.get("expand", {}).get("brand_id")
        # Also try campaign.expand.product_id.expand.brand_id
        if not brand_data and expand.get("product_id"):
            brand_data = expand["product_id"].get("expand", {}).get("brand_id")

        if brand_data:
            return brand_data, None

        # Fallback: fetch first brandRef from worksheet
        worksheet = context.get("worksheet", {})
        brand_refs = worksheet.get("brandRefs", [])
        if not brand_refs or len(brand_refs) == 0:
            return {}, None

        try:
            result = await execute_mcp_tool(
                "get_record",
                {"collection": "brand_identities", "record_id": brand_refs[0]},
            )
            brand, err = parse_mcp_result(result)
            return brand or {}, err
        except Exception as e:
            logger.warning(f"Failed to fetch brand identity: {e}")
            return {}, str(e)

    async def _fetch_customer():
        worksheet = context.get("worksheet", {})
        customer_refs = worksheet.get("customerRefs", [])
        if not customer_refs or len(customer_refs) == 0:
            return {}, None

        try:
            result = await execute_mcp_tool(
                "get_record",
                {"collection": "customer_personas", "record_id": customer_refs[0]},
            )
            profile, err = parse_mcp_result(result)
            return profile or {}, err
        except Exception as e:
            logger.warning(f"Failed to fetch customer profile: {e}")
            return {}, str(e)

    # Execute Phase 2 fetches in parallel
    brand_task = asyncio.create_task(_fetch_brand())
    customer_task = asyncio.create_task(_fetch_customer())

    (brand_res, brand_err), (customer_res, customer_err) = await asyncio.gather(brand_task, customer_task)

    context["brandIdentity"] = brand_res
    if brand_err: errors["brandIdentity"] = brand_err

    context["customerProfile"] = customer_res
    if customer_err: errors["customerProfile"] = customer_err

    return context, errors
