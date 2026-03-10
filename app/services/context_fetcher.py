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

    worksheet_data = expand.get("worksheet_id")
    worksheet_id = campaign_data.get("worksheet_id") if not worksheet_data else None

    product_data = expand.get("product_id")
    product_id = campaign_data.get("product_id") if not product_data else None

    # PHASE 1: Fetch Worksheet & Product concurrently
    async def fetch_ws():
        if worksheet_data:
            return worksheet_data, ""
        if worksheet_id:
            try:
                res = await execute_mcp_tool(
                    "get_record", {"collection": "worksheets", "record_id": worksheet_id}
                )
                ws, err = parse_mcp_result(res)
                return ws or {}, err or ""
            except Exception as e:
                logger.warning(f"Failed to fetch worksheet: {e}")
                return {}, str(e)
        return {}, ""

    async def fetch_prod():
        if product_data:
            return product_data, ""
        if product_id:
            try:
                res = await execute_mcp_tool(
                    "get_record",
                    {
                        "collection": "products_services",
                        "record_id": product_id,
                        "expand": "brand_id",
                    },
                )
                prod, err = parse_mcp_result(res)
                return prod or {}, err or ""
            except Exception as e:
                logger.warning(f"Failed to fetch product: {e}")
                return {}, str(e)
        return {}, ""

    (ws_res, ws_err), (prod_res, prod_err) = await asyncio.gather(fetch_ws(), fetch_prod())

    context["worksheet"] = ws_res
    if ws_err:
        errors["worksheet"] = ws_err

    context["product"] = prod_res
    if prod_err:
        errors["product"] = prod_err

    # PHASE 2: Fetch Brand Identity & Customer Profile concurrently
    brand_data = None
    if context["product"]:
        brand_data = context["product"].get("expand", {}).get("brand_id")
    if not brand_data and expand.get("product_id"):
        brand_data = expand["product_id"].get("expand", {}).get("brand_id")

    brand_id_to_fetch = None
    if not brand_data:
        brand_refs = context["worksheet"].get("brandRefs", [])
        if brand_refs and len(brand_refs) > 0:
            brand_id_to_fetch = brand_refs[0]

    customer_refs = context["worksheet"].get("customerRefs", [])
    customer_id_to_fetch = customer_refs[0] if customer_refs and len(customer_refs) > 0 else None

    async def fetch_brand():
        if brand_data:
            return brand_data, ""
        if brand_id_to_fetch:
            try:
                res = await execute_mcp_tool(
                    "get_record", {"collection": "brand_identities", "record_id": brand_id_to_fetch}
                )
                b, err = parse_mcp_result(res)
                return b or {}, err or ""
            except Exception as e:
                logger.warning(f"Failed to fetch brand identity: {e}")
                return {}, str(e)
        return {}, ""

    async def fetch_customer():
        if customer_id_to_fetch:
            try:
                res = await execute_mcp_tool(
                    "get_record", {"collection": "customer_personas", "record_id": customer_id_to_fetch}
                )
                c, err = parse_mcp_result(res)
                return c or {}, err or ""
            except Exception as e:
                logger.warning(f"Failed to fetch customer profile: {e}")
                return {}, str(e)
        return {}, ""

    (brand_res, brand_err), (cust_res, cust_err) = await asyncio.gather(fetch_brand(), fetch_customer())

    context["brandIdentity"] = brand_res
    if brand_err:
        errors["brandIdentity"] = brand_err

    context["customerProfile"] = cust_res
    if cust_err:
        errors["customerProfile"] = cust_err

    return context, errors
