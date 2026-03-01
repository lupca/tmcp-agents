from typing import Dict, Any, List

# Mock Data Tools

def fetch_branch_data() -> Dict[str, str]:
    """Mock fetch branch data."""
    return {"branchName": "Downtown Office", "location": "New York, NY"}

def fetch_worksheet() -> Dict[str, Any]:
    """Mock fetch worksheet data."""
    return {
        "businessDescription": "A premium coffee shop serving artisanal blends.",
        "targetAudience": "Young professionals and coffee enthusiasts.",
        "painPoints": ["Lack of quality coffee nearby", "Need a quiet place to work"],
        "uniqueSellingProposition": "Locally roasted beans and a cozy atmosphere.",
        "language": "English"
    }

def fetch_customer_profile() -> Dict[str, Any]:
    """Mock fetch customer profile."""
    return {
        "personaName": "Sarah the Student",
        "goalsAndMotivations": ["Finish thesis", "Enjoy good coffee"],
        "painPointsAndChallenges": ["Expensive coffee", "No wifi"],
        "demographics": {"age": "20-25", "occupation": "Student"}
    }

def fetch_brand_identity() -> Dict[str, Any]:
    """Mock fetch brand identity."""
    return {
        "brandName": "Brew Haven",
        "missionStatement": "To provide a sanctuary for coffee lovers.",
        "keywords": ["Cozy", "Artisanal", "Community", "Premium"]
    }

def fetch_campaign() -> Dict[str, Any]:
    """Mock fetch campaign data."""
    return {
        "name": "Summer Launch",
        "goal": "Increase foot traffic by 20%",
        "toneOfVoice": "Exciting and welcoming"
    }

def fetch_event() -> Dict[str, Any]:
    """Mock fetch event data."""
    return {
        "title": "Summer Cold Brew Fest",
        "eventType": "Festival",
        "aiAnalysis": "High engagement potential due to seasonal relevance.",
        "contentSuggestion": "Focus on refreshing visuals and limited-time offers."
    }

def search_web(query: str) -> List[Dict[str, str]]:
    """Mock web search."""
    return [
        {"title": "Top Coffee Trends 2024", "snippet": "Cold brew is still king...", "url": "https://example.com/coffee-trends"},
        {"title": "How to market coffee shops", "snippet": "Engage with your local community...", "url": "https://example.com/marketing-tips"}
    ]

def rag_search(query: str) -> str:
    """Mock RAG search for evaluation."""
    return "Best practices for coffee shop marketing include high-quality images and engaging questi1ons."

