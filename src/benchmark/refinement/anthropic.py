import logging
import time

from anthropic import AsyncAnthropic

from .base import BaseRefiner, PromptConfig, RefinementResult, TruncatedResponseError

logger = logging.getLogger("benchmark")


class AnthropicRefiner(BaseRefiner):
    provider = "anthropic"

    def __init__(self, model: str = "claude-opus-4-7", temperature: float = 0.0) -> None:
        self.model = model
        self.temperature = temperature
        self.client = AsyncAnthropic()

    async def refine(self, transcription: str, prompt: PromptConfig) -> RefinementResult:
        messages = []
        if prompt.examples:
            for ex in prompt.examples:
                messages.append({"role": "user", "content": ex["input"]})
                messages.append({"role": "assistant", "content": ex["output"]})
        messages.append({"role": "user", "content": prompt.format_user(transcription)})

        start = time.monotonic()
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=prompt.system,
            messages=messages,
            temperature=self.temperature,
        )
        elapsed = (time.monotonic() - start) * 1000

        if response.stop_reason == "max_tokens":
            raise TruncatedResponseError(
                f"Anthropic {self.model} truncou a resposta (stop_reason=max_tokens)"
            )

        tokens = response.usage.input_tokens + response.usage.output_tokens
        logger.debug(f"Anthropic {self.model} — tokens: {tokens}, time: {elapsed:.0f}ms")
        return RefinementResult(
            refined_text=response.content[0].text.strip(),
            tokens_used=tokens,
            response_time_ms=elapsed,
        )
