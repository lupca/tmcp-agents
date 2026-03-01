import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import asyncio
import json
import httpx

async def test_streaming():
    url = "http://localhost:8000/chat"
    payload = {
        "message": "Dựa vào chiến lược marketing có id 1234 hãy viết 1 bài blog cho chiến dịch này.",
        "thread_id": "demo_thread_1"
    }

    print(f"Connecting to {url}...")
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", url, json=payload) as response:
                print(f"Connection status: {response.status_code}")
                if response.status_code != 200:
                    print(f"Error: {await response.read()}")
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                            print(f"Server Event: {data}")
                        except json.JSONDecodeError:
                            print(f"Raw Data: {data_str}")
    except Exception as e:
        print(f"Request failed: {e}")
        print("\nMake sure the API server is running with: uvicorn app:app --reload")

if __name__ == "__main__":
    asyncio.run(test_streaming())
