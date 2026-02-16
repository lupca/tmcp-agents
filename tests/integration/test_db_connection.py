import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import asyncio
from app.tools.mcp_bridge import list_records

async def test_db():
    collections = [
        "business_ideas",
        "brand_identities",
        "customer_profiles",
        "marketing_campaigns",
        "campaign_tasks",
        "content_calendar_events",
        "social_posts"
    ]
    
    print("Verifying Database Records...")
    for col in collections:
        try:
            records = await list_records.invoke({"collection": col})
            print(f"\n--- {col} ---")
            print(records[:500]) # Print first 500 chars
        except Exception as e:
            print(f"Error listing {col}: {e}")

if __name__ == "__main__":
    asyncio.run(test_db())
