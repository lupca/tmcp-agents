import asyncio
import json
import httpx

async def test():
    try:
        url = 'http://127.0.0.1:8090/api/collections/brand_identities/records?perPage=1'
        print('Fetching Brand from PocketBase...')
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            data = resp.json()
            brands = data.get('items', [])
            if not brands:
                print('No brands found.')
                return
            brand_id = brands[0]['id']
            print(f'Using Brand ID: {brand_id}')
            print('Brand Data:', json.dumps(brands[0], indent=2))
        
        # Call customer profile endpoint
        print('\nRequesting Customer Profile generation...')
        url_agent = 'http://127.0.0.1:8000/generate-customer-profile'
        data_agent = {'brand_identity_id': brand_id, 'language': 'Vietnamese', 'auth_token': ''}
        
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream('POST', url_agent, json=data_agent) as response:
                async for chunk in response.aiter_text():
                    print(chunk, end='')
    except Exception as e:
        print(f'Error: {e}')

asyncio.run(test())
