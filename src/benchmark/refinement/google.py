import asyncio
import logging
import os
import time

from google import genai
from google.genai import types

from .base import BaseRefiner, PromptConfig, RefinementResult, TruncatedResponseError

logger = logging.getLogger("benchmark")


class GoogleRefiner(BaseRefiner):
    provider = "google"

    def __init__(self, model: str = "gemini-2.0-flash", temperature: float = 0.0) -> None:
        self.model = model
        self.temperature = temperature
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY", ""))

    def _call_sync(
        self, transcription: str, prompt: PromptConfig, metadata: dict | None = None
    ) -> tuple[str, int | None, float]:
        contents: list[types.Content] = []
        if prompt.examples:
            for ex in prompt.examples:
                contents.append(types.Content(role="user", parts=[types.Part(text=ex["input"])]))
                contents.append(types.Content(role="model", parts=[types.Part(text=ex["output"])]))
        contents.append(
            types.Content(role="user", parts=[types.Part(text=prompt.format_user(transcription, metadata))])
        )

        start = time.monotonic()
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=prompt.system,
                temperature=self.temperature,
            ),
        )
        elapsed = (time.monotonic() - start) * 1000

        if (
            response.candidates
            and response.candidates[0].finish_reason is not None
            and response.candidates[0].finish_reason.name == "MAX_TOKENS"
        ):
            raise TruncatedResponseError(
                f"Google {self.model} truncou a resposta (finish_reason=MAX_TOKENS)"
            )

        tokens = None
        if response.usage_metadata:
            tokens = response.usage_metadata.total_token_count

        return response.text.strip(), tokens, elapsed

    async def refine(
        self, transcription: str, prompt: PromptConfig, metadata: dict | None = None
    ) -> RefinementResult:
        text, tokens, elapsed = await asyncio.to_thread(self._call_sync, transcription, prompt, metadata)
        logger.debug(f"Google {self.model} — tokens: {tokens}, time: {elapsed:.0f}ms")
        return RefinementResult(refined_text=text, tokens_used=tokens, response_time_ms=elapsed)
