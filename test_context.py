import asyncio
import json
from app.services.context_fetcher import fetch_campaign_context
from app.tools.mcp_bridge import auth_token_var, execute_mcp_tool, parse_mcp_result

async def main():
    auth_token_var.set("")
    camp_id = "9b7fcx0b4qtlc7t"
    print(f"Testing with campaign ID: {camp_id}")
    
    ctx, errs = await fetch_campaign_context(camp_id)
    print("CONTEXT:")
    print(json.dumps(ctx, indent=2))
    print("ERRORS:")
    print(json.dumps(errs, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
