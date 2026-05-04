import logging
import time

from openai import AsyncOpenAI

from .base import BaseRefiner, PromptConfig, RefinementResult

logger = logging.getLogger("benchmark")


class OpenAIRefiner(BaseRefiner):
    provider = "openai"

    def __init__(self, model: str = "gpt-4o", temperature: float = 0.0) -> None:
        self.model = model
        self.temperature = temperature
        self.client = AsyncOpenAI()

    async def refine(self, transcription: str, prompt: PromptConfig) -> RefinementResult:
        messages = []
        if prompt.examples:
            for ex in prompt.examples:
                messages.append({"role": "user", "content": ex["input"]})
                messages.append({"role": "assistant", "content": ex["output"]})
        messages.append({"role": "user", "content": prompt.format_user(transcription)})

        start = time.monotonic()
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": prompt.system}] + messages,
            temperature=self.temperature,
        )
        elapsed = (time.monotonic() - start) * 1000

        logger.debug(f"OpenAI {self.model} — tokens: {response.usage.total_tokens}, time: {elapsed:.0f}ms")
        return RefinementResult(
            refined_text=response.choices[0].message.content.strip(),
            tokens_used=response.usage.total_tokens,
            response_time_ms=elapsed,
        )
