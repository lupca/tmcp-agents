import json
import asyncio
from typing import AsyncGenerator

from langchain_core.messages import SystemMessage, HumanMessage 
from app.tools.mcp_bridge import execute_mcp_tool

from app.core.llm_factory import get_ollama_llm
from marketing_team.prompts import MARKETING_STRATEGY_PROMPT
from app.utils.sse import sse_event
from app.utils.llm import parse_json_response

async def marketing_strategy_event_generator(
    worksheet_id: str,
    campaign_type: str = "awareness",
    product_id: str = "",
    goal: str = "",
    language: str = "Vietnamese",
    auth_token: str = "",
) -> AsyncGenerator[str, None]:
    """
    Orchestrate the AI agent to generate a Marketing Strategy.
    Fetches Worksheet + Brand + ICP via MCP, then streams LLM output.
    """
    try:
        # --- Step 1: Fetch all contexts ---

        def _mcp_args(collection: str, record_id: str) -> dict:
            args = {"collection": collection, "record_id": record_id}
            if auth_token:
                args["auth_token"] = auth_token
            return args

        # 1. Fetch Worksheet
        yield sse_event("status", status="fetching_worksheet", agent="MarketingStrategist")
        try:
            ws_result = await execute_mcp_tool("get_record", _mcp_args("worksheets", worksheet_id))
            ws_data_raw = ws_result.content[0].text
            ws_parsed = json.loads(ws_data_raw)
            worksheet_content = ws_parsed.get("content", "")
            
            # Extract brand and customer refs
            brand_refs = ws_parsed.get("brandRefs", [])
            customer_refs = ws_parsed.get("customerRefs", [])
            
            if not brand_refs:
                raise ValueError("Worksheet has no associated Brand Identity.")
            if not customer_refs:
                raise ValueError("Worksheet has no associated Customer Profile.")
                
            brand_identity_id = brand_refs[0]
            customer_profile_id = customer_refs[0]
        except Exception as e:
            yield sse_event("error", error=f"Failed to fetch worksheet: {str(e)}")
            return

        # 2. Fetch Brand, ICP, and Product in parallel
        yield sse_event("status", status="fetching_brand", agent="MarketingStrategist")
        yield sse_event("status", status="fetching_icp", agent="MarketingStrategist")
        if product_id:
            yield sse_event("status", status="fetching_product", agent="MarketingStrategist")

        async def fetch_brand():
            return await execute_mcp_tool("get_record", _mcp_args("brand_identities", brand_identity_id))

        async def fetch_icp():
            return await execute_mcp_tool("get_record", _mcp_args("customer_personas", customer_profile_id))

        async def fetch_product():
            return await execute_mcp_tool("get_record", _mcp_args("products_services", product_id))

        tasks = [fetch_brand(), fetch_icp()]
        if product_id:
            tasks.append(fetch_product())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        brand_result_or_exc = results[0]
        icp_result_or_exc = results[1]
        product_result_or_exc = results[2] if product_id else None

        # Process Brand
        if isinstance(brand_result_or_exc, Exception):
            yield sse_event("error", error=f"Failed to fetch brand identity: {str(brand_result_or_exc)}")
            return

        try:
            brand_data_raw = brand_result_or_exc.content[0].text
            brand_parsed = json.loads(brand_data_raw)
        except Exception as e:
            yield sse_event("error", error=f"Failed to parse brand identity: {str(e)}")
            return

        # Process ICP
        if isinstance(icp_result_or_exc, Exception):
            yield sse_event("error", error=f"Failed to fetch customer profile: {str(icp_result_or_exc)}")
            return

        try:
            icp_data_raw = icp_result_or_exc.content[0].text
            icp_parsed = json.loads(icp_data_raw)
        except Exception as e:
            yield sse_event("error", error=f"Failed to parse customer profile: {str(e)}")
            return

        # Process Product
        product_parsed = {}
        if product_id:
            if isinstance(product_result_or_exc, Exception):
                print(f"Failed to fetch product: {str(product_result_or_exc)}")
            else:
                try:
                    product_data_raw = product_result_or_exc.content[0].text
                    product_parsed = json.loads(product_data_raw)
                except Exception as e:
                    print(f"Failed to parse product: {str(e)}")

        # --- Step 4: Build Prompt ---
        yield sse_event("status", status="analyzing", agent="MarketingStrategist")

        def safe_dump(obj):
            try:
                return json.dumps(obj, ensure_ascii=False) if obj else ""
            except Exception:
                return str(obj)

        # Format custom prompt section if goal is present
        custom_prompt_section = ""
        if goal:
            custom_prompt_section = f"""
4.  **Specific User Request:**
    ---
    The user has provided a specific focus. Prioritize this request in your output: "{goal}"
    ---
"""

        core_messaging = brand_parsed.get("core_messaging", {})
        psychographics = icp_parsed.get("psychographics", {})

        product_context = ""
        if product_parsed:
            product_context = f"""
    - Product Name: {product_parsed.get('name', '')}
    - USP: {product_parsed.get('usp', '')}
    - Key Features: {safe_dump(product_parsed.get('key_features', []))}
    - Key Benefits: {safe_dump(product_parsed.get('key_benefits', []))}
"""

        # Re-formatting with safe dumps
        prompt = MARKETING_STRATEGY_PROMPT.format(
            worksheetContent=worksheet_content,
            brandName=brand_parsed.get("brand_name", "") or brand_parsed.get("brandName", ""),
            missionStatement=core_messaging.get("mission_statement", ""),
            keywords=safe_dump(core_messaging.get("keywords", [])),
            personaName=icp_parsed.get("persona_name", "") or icp_parsed.get("personaName", ""),
            icpSummary=icp_parsed.get("summary", ""),
            goals=safe_dump(psychographics.get("goals", [])),
            painPoints=safe_dump(psychographics.get("pain_points", [])),
            interests=safe_dump(psychographics),
            campaignType=campaign_type,
            productContext=product_context,
            customPromptSection=custom_prompt_section,
            language=language
        )

        llm = get_ollama_llm(temperature=0.7)
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Generate the marketing strategy based on the above context.")
        ]

        # --- Step 5: Stream Tokens ---
        full_content = ""
        async for chunk in llm.astream(messages):
            full_content += chunk.content
            yield sse_event("chunk", content=chunk.content)

        # --- Step 6: Finalize (Parse JSON) ---
        try:
            strategy_data = parse_json_response(full_content)
            yield sse_event("done", marketingStrategy=strategy_data)
        except ValueError as e:
            yield sse_event("error", error=f"Generated content was not valid JSON: {str(e)}")

    except Exception as e:
        yield sse_event("error", error=str(e))
