import asyncio
from app.tools.mcp_bridge import auth_token_var, execute_mcp_tool

async def main():
    auth_token_var.set("")
    res = await execute_mcp_tool("get_collection_schema", {"collection": "marketing_campaigns"})
    print(res.content[0].text)
        
if __name__ == "__main__":
    asyncio.run(main())
