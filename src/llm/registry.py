from dataclasses import dataclass


@dataclass
class ModelConfig:
    name: str
    provider: str
    model: str


MODELS = {
    "groq": ModelConfig(name="groq", provider="groq", model="llama-3.3-70b-versatile"),
    "ollama": ModelConfig(name="ollama", provider="ollama", model="llama3.1:8b"),
    "openai": ModelConfig(name="openai", provider="openai", model="gpt-4o"),
    "anthropic": ModelConfig(name="anthropic", provider="anthropic", model="claude-haiku-4-5-20251001"),
    "anthropic_sonnet": ModelConfig(name="anthropic_sonnet", provider="anthropic", model="claude-sonnet-5"),
}
