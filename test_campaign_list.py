import asyncio
import json
from app.tools.mcp_bridge import auth_token_var, execute_mcp_tool, parse_mcp_result

async def main():
    auth_token_var.set("")
    res = await execute_mcp_tool("list_records", {"collection": "marketing_campaigns", "expand": "product_id,worksheet_id", "per_page": 100})
    data, _ = parse_mcp_result(res)
    campaigns = data.get("items", []) if data else []
    
    print(f"Total campaigns: {len(campaigns)}")
    valid_camps = []
    for c in campaigns:
        p_id = c.get("product_id") or ""
        w_id = c.get("worksheet_id") or ""
        if p_id or w_id:
            valid_camps.append(c)
            print(f"- Campaign {c['id']} ({c['name']}) has product_id: '{p_id}', worksheet_id: '{w_id}'")
            print(f"   Expand: {c.get('expand', {})}")
            
    if not valid_camps:
        print("NONE of the campaigns have product_id or worksheet_id.")
        
if __name__ == "__main__":
    asyncio.run(main())
