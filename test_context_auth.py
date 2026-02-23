import asyncio
import json
import httpx
from app.services.context_fetcher import fetch_campaign_context
from app.tools.mcp_bridge import auth_token_var

async def main():
    async with httpx.AsyncClient() as client:
        # 1. Login to get real token
        r = await client.post("http://127.0.0.1:8090/api/collections/users/auth-with-password", json={
            "identity": "user@tmcp.com", # Replace with actual credentials if needed, or maybe admin
            "password": "1234567890" # Replace if different
        })
        
        if r.status_code != 200:
            print("Login failed:", r.text)
            return
            
        token = r.json()["token"]
        print("Logged in successfully. Token length:", len(token))
        
        # 2. Set token in context var (this is what the endpoint does)
        auth_token_var.set(token)
        
        # 3. Test Campaign ID with Worksheet attached
        camp_id = "9b7fcx0b4qtlc7t"
        print(f"Testing with campaign ID: {camp_id}")
        
        ctx, errs = await fetch_campaign_context(camp_id)
        print("CONTEXT:")
        print(json.dumps(ctx, indent=2))
        print("ERRORS:")
        print(json.dumps(errs, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
