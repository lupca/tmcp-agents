import asyncio
from pocketbase import PocketBase

async def test():
    pb = PocketBase("http://127.0.0.1:8090")
    pb.admins.auth_with_password("admin@tmcp.com", "admin1234") # Assuming typical dev admin
    
    try:
        camp = pb.collection("marketing_campaigns").get_one("9b7fcx0b4qtlc7t", expand="worksheet_id")
        print("Campaign Expand Keys:", list(camp.expand.keys()) if camp.expand else None)
        ws = camp.expand.get("worksheet_id") if camp.expand else None
        if ws:
            print("Worksheet keys:", list(ws.keys()))
            print("Brand Refs:", ws.get("brandRefs"))
            print("Customer Refs:", ws.get("customerRefs"))
        else:
            print("No expanded worksheet!")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(test())
