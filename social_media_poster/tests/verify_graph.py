import asyncio
from social_media_poster.graph import social_media_graph

async def main():
    print("--- Starting Social Media Flow Verification ---")
    
    initial_state = {
        "messages": [("user", "Create a post for the Summer Launch")],
        "context_data": {},
        "generated_post": None
    }
    
    print("Invoking graph...")
    config = {"configurable": {"thread_id": "verify_thread_1"}}
    async for event in social_media_graph.astream(initial_state, config=config):
        for key, value in event.items():
            print(f"\n--- Node: {key} ---")
            if key == "Retriever":
                print("Context retrieved.")
                # print(value.get("context_data").keys()) 
            elif key == "PostGenerator":
                print(f"Generated Post: {value.get('generated_post')[:50]}...")
            elif key == "Evaluator":
                print(f"Feedback: {value.get('feedback')}")
                print(f"Next Node: {value.get('next_node')}")

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(main())
