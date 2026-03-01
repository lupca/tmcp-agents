from typing import Dict, Any
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

from .state import SocialMediaState
from .tools import (
    fetch_branch_data,
    fetch_worksheet,
    fetch_customer_profile,
    fetch_brand_identity,
    fetch_campaign,
    fetch_event,
    search_web,
    rag_search
)

# Initialize LLM
llm = ChatOllama(model="qwen2.5:latest", temperature=0.7)

def content_retriever_node(state: SocialMediaState) -> Dict[str, Any]:
    """
    Retriever (R): Gathers context data from mocked MCP tools and web search.
    """
    print("--- [R] Content Retriever Node ---")
    
    # Fetch all context
    context = {
        "branch": fetch_branch_data(),
        "worksheet": fetch_worksheet(),
        "customerProfile": fetch_customer_profile(),
        "brandIdentity": fetch_brand_identity(),
        "campaign": fetch_campaign(),
        "event": fetch_event(),
        "web_search_results": search_web("coffee marketing trends")
    }
    
    # RAG search for additional context (simulated)
    rag_context = rag_search("coffee shop social media best practices")
    context["rag_context"] = rag_context
    
    return {"context_data": context}

def post_generator_node(state: SocialMediaState) -> Dict[str, Any]:
    """
    Generator (G): Generates a social media post based on the retrieved context.
    """
    print("--- [G] Post Generator Node ---")
    
    context = state.get("context_data", {})
    platform = "Instagram" # Default for now, could be dynamic
    language = context.get("worksheet", {}).get("language", "English")
    
    # Construct the prompt based on the user's requirements
    prompt_template = """
    **Persona:** You are an expert content strategist and copywriter, known for creating platform-specific content that drives results across all stages of the marketing funnel (Awareness, Engagement, Consideration, Conversion).

    **Task:** Craft a compelling piece of content for the specified platform: **{platform}**.

    **Context:**
    Deeply analyze all the provided context to inform your writing:
    - **Platform:** {platform}
    - **Language:** The generated content must be in the following language: **{language}**.
    - **Brand:** {brand_name}, Mission: {mission}, Keywords: {keywords}
    - **Audience (ICP):** Persona: {persona_name}, Goals: {goals}, Pains: {pains}
    - **Campaign:** Name: '{campaign_name}', Goal: '{campaign_goal}', Tone: '{campaign_tone}'
    - **Specific Event/Topic:**
        - Title: '{event_title}'
        - Type: '{event_type}'
        - AI Rationale: '{event_ai}'
        - Initial Suggestion: '{event_suggestion}'
    - **Web Search Findings:** {web_search}
    - **RAG Context:** {rag_context}

    **Instructions & Rules:**
    1.  Create a post that resonates with the audience and aligns with the brand identity.
    2.  Use the tone of voice specified in the campaign.
    3.  **Output Format:** Return only the generated post content. Do not add any other text or explanations.
    """
    
    # Safely extract values for formatting
    try:
        formatted_prompt = prompt_template.format(
            platform=platform,
            language=language,
            brand_name=context.get("brandIdentity", {}).get("brandName", ""),
            mission=context.get("brandIdentity", {}).get("missionStatement", ""),
            keywords=context.get("brandIdentity", {}).get("keywords", []),
            persona_name=context.get("customerProfile", {}).get("personaName", ""),
            goals=context.get("customerProfile", {}).get("goalsAndMotivations", []),
            pains=context.get("customerProfile", {}).get("painPointsAndChallenges", []),
            campaign_name=context.get("campaign", {}).get("name", ""),
            campaign_goal=context.get("campaign", {}).get("goal", ""),
            campaign_tone=context.get("campaign", {}).get("toneOfVoice", ""),
            event_title=context.get("event", {}).get("title", ""),
            event_type=context.get("event", {}).get("eventType", ""),
            event_ai=context.get("event", {}).get("aiAnalysis", ""),
            event_suggestion=context.get("event", {}).get("contentSuggestion", ""),
            web_search=context.get("web_search_results", []),
            rag_context=context.get("rag_context", "")
        )
    except Exception as e:
        print(f"Error formatting prompt: {e}")
        formatted_prompt = "Generate a social media post for a coffee shop."

    # Call LLM
    response = llm.invoke([HumanMessage(content=formatted_prompt)])
    
    return {"generated_post": response.content}

def evaluator_node(state: SocialMediaState) -> Dict[str, Any]:
    """
    Evaluator (E): Evaluates the retrieved data and the post with RAG.
    """
    print("--- [E] Evaluator Node ---")
    
    generated_post = state.get("generated_post")
    context_data = state.get("context_data", {})
    
    # 1. Evaluate Context (if no post generated yet)
    if not generated_post:
        print("Evaluating Context Data...")
        # Check if we have enough data (Mock check)
        if not context_data.get("worksheet") or not context_data.get("campaign"):
            return {"next_node": "Retriever", "feedback": "Missing critical context (Worksheet or Campaign)."}
        
        # If context is good, proceed to Generator
        return {"next_node": "PostGenerator", "feedback": "Context approved. Proceed to generation."}

    # 2. Evaluate Generated Post
    else:
        print("Evaluating Generated Post...")
        evaluation_prompt = f"""
        You are a strict editor. Evaluate this social media post:
        "{generated_post}"
        
        Using the context: {context_data.get('rag_context', 'No RAG context')}
        
        Does it meet these criteria?
        1. Engaging?
        2. Relevant to coffee lovers?
        3. Clear call to action?
        
        If YES, respond with "APPROVED".
        If NO, respond with "RETRY: <reason>".
        """
        
        response = llm.invoke([HumanMessage(content=evaluation_prompt)])
        decision = response.content
        
        print(f"Evaluation Decision: {decision}")
        
        if "APPROVED" in decision.upper():
            return {"next_node": "FINISH", "feedback": decision}
        else:
            return {"next_node": "PostGenerator", "feedback": decision}

