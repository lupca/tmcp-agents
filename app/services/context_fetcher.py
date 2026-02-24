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

    # Helper functions for fetching components
    async def fetch_worksheet_task(ws_id: str) -> Tuple[Dict[str, Any], str]:
        try:
            res = await execute_mcp_tool(
                "get_record",
                {"collection": "worksheets", "record_id": ws_id},
            )
            return parse_mcp_result(res)
        except Exception as e:
            logger.warning(f"Failed to fetch worksheet: {e}")
            return {}, str(e)

    async def fetch_product_task(prod_id: str) -> Tuple[Dict[str, Any], str]:
        try:
            res = await execute_mcp_tool(
                "get_record",
                {
                    "collection": "products_services",
                    "record_id": prod_id,
                    "expand": "brand_id",
                },
            )
            return parse_mcp_result(res)
        except Exception as e:
            logger.warning(f"Failed to fetch product: {e}")
            return {}, str(e)

    # 2. Parallel Fetch: Worksheet & Product
    tasks = []
    task_map = {}

    # Check if Worksheet is in expand or needs fetching
    worksheet_data = expand.get("worksheet_id")
    if worksheet_data:
        context["worksheet"] = worksheet_data
    else:
        worksheet_id = campaign_data.get("worksheet_id")
        if worksheet_id:
            tasks.append(fetch_worksheet_task(worksheet_id))
            task_map["worksheet"] = len(tasks) - 1
        else:
            context["worksheet"] = {}

    # Check if Product is in expand or needs fetching
    product_data = expand.get("product_id")
    if product_data:
        context["product"] = product_data
    else:
        product_id = campaign_data.get("product_id")
        if product_id:
            tasks.append(fetch_product_task(product_id))
            task_map["product"] = len(tasks) - 1
        else:
            context["product"] = {}

    if tasks:
        fetch_results = await asyncio.gather(*tasks)

        if "worksheet" in task_map:
            ws, err = fetch_results[task_map["worksheet"]]
            context["worksheet"] = ws or {}
            if err:
                errors["worksheet"] = err

        if "product" in task_map:
            prod, err = fetch_results[task_map["product"]]
            context["product"] = prod or {}
            if err:
                errors["product"] = err

    # 3. Determine Brand and Customer Profile needs

    # Brand Logic
    brand_data = None
    product = context.get("product", {})
    if product:
        brand_data = product.get("expand", {}).get("brand_id")
    if not brand_data and expand.get("product_id"):
        brand_data = expand["product_id"].get("expand", {}).get("brand_id")

    if brand_data:
        context["brandIdentity"] = brand_data

    worksheet = context.get("worksheet", {})

    # Prepare Phase 3 Tasks
    async def fetch_brand_task(brand_id: str) -> Tuple[Dict[str, Any], str]:
        try:
            res = await execute_mcp_tool(
                "get_record",
                {"collection": "brand_identities", "record_id": brand_id},
            )
            return parse_mcp_result(res)
        except Exception as e:
            logger.warning(f"Failed to fetch brand identity: {e}")
            return {}, str(e)

    async def fetch_customer_task(cust_id: str) -> Tuple[Dict[str, Any], str]:
        try:
            res = await execute_mcp_tool(
                "get_record",
                {"collection": "customer_personas", "record_id": cust_id},
            )
            return parse_mcp_result(res)
        except Exception as e:
            logger.warning(f"Failed to fetch customer profile: {e}")
            return {}, str(e)

    tasks_p3 = []
    task_map_p3 = {}

    # Check if we need to fetch Brand (fallback)
    if not brand_data:
        brand_refs = worksheet.get("brandRefs", [])
        if brand_refs and len(brand_refs) > 0:
            tasks_p3.append(fetch_brand_task(brand_refs[0]))
            task_map_p3["brandIdentity"] = len(tasks_p3) - 1
        else:
            context["brandIdentity"] = {}

    # Check if we need to fetch Customer Profile
    customer_refs = worksheet.get("customerRefs", [])
    if customer_refs and len(customer_refs) > 0:
        tasks_p3.append(fetch_customer_task(customer_refs[0]))
        task_map_p3["customerProfile"] = len(tasks_p3) - 1
    else:
        context["customerProfile"] = {}

    if tasks_p3:
        p3_results = await asyncio.gather(*tasks_p3)

        if "brandIdentity" in task_map_p3:
            brand, err = p3_results[task_map_p3["brandIdentity"]]
            context["brandIdentity"] = brand or {}
            if err:
                errors["brandIdentity"] = err

        if "customerProfile" in task_map_p3:
            cust, err = p3_results[task_map_p3["customerProfile"]]
            context["customerProfile"] = cust or {}
            if err:
                errors["customerProfile"] = err

    return context, errors
