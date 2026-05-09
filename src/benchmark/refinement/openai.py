import logging
import time

from openai import AsyncOpenAI

from .base import BaseRefiner, PromptConfig, RefinementResult, TruncatedResponseError

logger = logging.getLogger("benchmark")


class OpenAIRefiner(BaseRefiner):
    provider = "openai"

    def __init__(self, model: str = "gpt-4o", temperature: float = 0.0) -> None:
        self.model = model
        self.temperature = temperature
        self.client = AsyncOpenAI()

    async def refine(
        self, transcription: str, prompt: PromptConfig, metadata: dict | None = None
    ) -> RefinementResult:
        messages = []
        if prompt.examples:
            for ex in prompt.examples:
                messages.append({"role": "user", "content": ex["input"]})
                messages.append({"role": "assistant", "content": ex["output"]})
        messages.append({"role": "user", "content": prompt.format_user(transcription, metadata)})

        start = time.monotonic()
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": prompt.system}] + messages,
            temperature=self.temperature,
            max_tokens=4096,
        )
        elapsed = (time.monotonic() - start) * 1000

        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise TruncatedResponseError(
                f"OpenAI {self.model} truncou a resposta (finish_reason=length)"
            )

        logger.debug(f"OpenAI {self.model} — tokens: {response.usage.total_tokens}, time: {elapsed:.0f}ms")
        return RefinementResult(
            refined_text=choice.message.content.strip(),
            tokens_used=response.usage.total_tokens,
            response_time_ms=elapsed,
        )
