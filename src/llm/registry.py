from dataclasses import dataclass


@dataclass
class ModelConfig:
    name: str
    provider: str
    model: str


MODELS = {
    # Groq removed llama-3.3-70b-versatile during the project (the first
    # Groq run used it). gpt-oss-120b is the closest model still on Groq,
    # so `TFG_MODEL=groq` keeps working, but note the model changed.
    "groq": ModelConfig(name="groq", provider="groq", model="openai/gpt-oss-120b"),
    "ollama": ModelConfig(name="ollama", provider="ollama", model="llama3.1:8b"),
    "openai": ModelConfig(name="openai", provider="openai", model="gpt-4o"),
    "anthropic": ModelConfig(name="anthropic", provider="anthropic", model="claude-haiku-4-5-20251001"),
    "anthropic_sonnet": ModelConfig(name="anthropic_sonnet", provider="anthropic", model="claude-sonnet-5"),
}
