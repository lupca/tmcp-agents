import os
import logging

logger = logging.getLogger(__name__)


def get_ollama_llm(temperature: float = 0, model: str = "qwen2.5"):
    """Create an Ollama LLM instance.

    Centralizes LLM creation so all modules share the same config.
    """
    from langchain_ollama import ChatOllama

    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.8:11434")
    return ChatOllama(model=model, temperature=temperature, base_url=ollama_base_url)
