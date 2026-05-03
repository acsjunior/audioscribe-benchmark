from .anthropic import AnthropicRefiner
from .base import BaseRefiner, PromptConfig, RefinementResult, load_prompt
from .google import GoogleRefiner
from .openai import OpenAIRefiner

REFINER_REGISTRY: dict[str, type[BaseRefiner]] = {
    "openai": OpenAIRefiner,
    "anthropic": AnthropicRefiner,
    "google": GoogleRefiner,
}


def get_refiner(provider: str, model: str) -> BaseRefiner:
    if provider not in REFINER_REGISTRY:
        raise ValueError(
            f"Unknown provider: '{provider}'. Available: {list(REFINER_REGISTRY)}"
        )
    return REFINER_REGISTRY[provider](model=model)
