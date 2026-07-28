import os

from dotenv import load_dotenv

from src.llm.registry import MODELS
from src.config.settings import settings

load_dotenv()


def build_llm(model_name: str | None = None, temperature: float = 0):
    model_name = model_name or settings.default_model
    config = MODELS[model_name]

    if config.provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=config.model, temperature=temperature)

    if config.provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=config.model, temperature=temperature)

    if config.provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=config.model, temperature=temperature)

    if config.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=config.model, temperature=temperature)

    raise ValueError(f"Unknown provider: {config.provider}")
