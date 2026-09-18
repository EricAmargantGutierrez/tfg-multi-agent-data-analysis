from dataclasses import dataclass


@dataclass
class ModelConfig:
    name: str
    provider: str
    model: str


MODELS = {
    "groq": ModelConfig(name="groq", provider="groq", model="openai/gpt-oss-120b"),
    "ollama": ModelConfig(name="ollama", provider="ollama", model="llama3.1:8b"),
    # Same size class as ollama (7.77B vs 8B), but trained with Spanish/
    # Catalan/Galician/Basque oversampled 2x -- picked specifically to
    # test whether ollama's language-vs-noise gap (results_and_failure_
    # analysis.md §8) is really about language training data.
    "salamandra": ModelConfig(name="salamandra", provider="ollama", model="hdnh2006/salamandra-7b-instruct"),
    "openai": ModelConfig(name="openai", provider="openai", model="gpt-4o"),
    "anthropic": ModelConfig(name="anthropic", provider="anthropic", model="claude-haiku-4-5-20251001"),
    "anthropic_sonnet": ModelConfig(name="anthropic_sonnet", provider="anthropic", model="claude-sonnet-5"),
}
