from unittest.mock import MagicMock

from openai.types import CompletionUsage
from openai.types.audio.transcription import UsageDuration, UsageTokens

from benchmark.usage import as_usage, usage_record


def test_openai_chat_usage_object():
    raw = CompletionUsage(prompt_tokens=900, completion_tokens=40, total_tokens=940)
    rec = usage_record(raw, 1234.4)
    assert rec["input_tokens"] == 900
    assert rec["output_tokens"] == 40
    assert rec["total_tokens"] == 940
    assert rec["response_time_ms"] == 1234
    assert rec["raw"]["prompt_tokens"] == 900


def test_openai_transcription_tokens_and_duration():
    tokens = UsageTokens(type="tokens", input_tokens=500, output_tokens=120, total_tokens=620)
    rec = usage_record(tokens, 10.0)
    assert (rec["input_tokens"], rec["output_tokens"], rec["total_tokens"]) == (500, 120, 620)
    assert rec["audio_seconds"] is None

    rec = usage_record(UsageDuration(type="duration", seconds=187.5), 10.0)
    assert rec["audio_seconds"] == 187.5
    assert rec["total_tokens"] is None


def test_gemini_dict_and_total_from_parts():
    rec = usage_record({"prompt_token_count": 300, "candidates_token_count": 50}, None)
    assert rec["total_tokens"] == 350
    assert rec["response_time_ms"] is None


def test_unknown_or_missing_usage():
    rec = usage_record(None, 5.0)
    assert rec["raw"] is None
    assert rec["total_tokens"] is None
    rec = usage_record(MagicMock(), 5.0)  # dublê sem dados: não quebra nem inventa números
    assert rec["raw"] is None
    assert rec["total_tokens"] is None


def test_as_usage():
    assert as_usage({"total_tokens": 1}) == {"total_tokens": 1}
    assert as_usage(MagicMock()) is None
    assert as_usage(None) is None
