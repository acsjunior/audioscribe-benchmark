from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from benchmark.transcription.whisper import (
    DEFAULT_PROMPT_GPT4O_TRANSCRIBE,
    WhisperTranscriber,
    _remove_hallucinations,
)


@pytest.fixture
def audio_file(tmp_path) -> Path:
    f = tmp_path / "audio.mp3"
    f.write_bytes(b"fake audio content")
    return f


@patch("benchmark.transcription.whisper.AsyncOpenAI")
async def test_transcribe_calls_api_with_correct_params(mock_openai_cls, audio_file):
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="As rosas não falam")
    )
    mock_openai_cls.return_value = mock_client

    transcriber = WhisperTranscriber(model="whisper-1")
    result = await transcriber.transcribe(audio_file)

    mock_client.audio.transcriptions.create.assert_called_once()
    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs["model"] == "whisper-1"
    assert call_kwargs["language"] == "pt"
    assert result == "As rosas não falam"


@patch("benchmark.transcription.whisper.AsyncOpenAI")
async def test_transcribe_uses_configured_model(mock_openai_cls, audio_file):
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="resultado")
    )
    mock_openai_cls.return_value = mock_client

    transcriber = WhisperTranscriber(model="whisper-1")
    await transcriber.transcribe(audio_file)

    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs["model"] == "whisper-1"


@patch("benchmark.transcription.whisper.AsyncOpenAI")
async def test_transcribe_removes_hallucinations(mock_openai_cls, audio_file):
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="As rosas não falam\nLegendas pela comunidade Amara.org")
    )
    mock_openai_cls.return_value = mock_client

    transcriber = WhisperTranscriber(model="whisper-1")
    result = await transcriber.transcribe(audio_file)

    assert "Amara" not in result
    assert result == "As rosas não falam"


@pytest.mark.parametrize("hallucination", [
    "Legendas pela comunidade Amara.org",
    "Amara.org",
    "Legendas: ",
    "Legendas:",
    "Transcrição: ",
    "Transcrição:",
    "Subtitles by the Amara.org community",
    "Tradução e legendas:",
    "Legendado por:",
    "Transcrição por:",
])
def test_remove_hallucinations_known_patterns(hallucination):
    text = f"As rosas não falam\n{hallucination}"
    assert _remove_hallucinations(text) == "As rosas não falam"


def test_remove_hallucinations_case_insensitive():
    assert _remove_hallucinations("letra\nLEGENDAS: ") == "letra"
    assert _remove_hallucinations("letra\nAMARA.ORG") == "letra"


def test_remove_hallucinations_clean_text_unchanged():
    text = "As rosas não falam\nApenas perfumam"
    assert _remove_hallucinations(text) == text


def test_remove_hallucinations_strips_whitespace():
    assert _remove_hallucinations("  As rosas não falam  ") == "As rosas não falam"


# --- _effective_prompt ---

def test_effective_prompt_whisper1_no_prompt():
    with patch("benchmark.transcription.whisper.AsyncOpenAI"):
        t = WhisperTranscriber(model="whisper-1")
    assert t._effective_prompt() is None


def test_effective_prompt_gpt4o_transcribe_no_prompt():
    with patch("benchmark.transcription.whisper.AsyncOpenAI"):
        t = WhisperTranscriber(model="gpt-4o-transcribe")
    assert t._effective_prompt() == DEFAULT_PROMPT_GPT4O_TRANSCRIBE


def test_effective_prompt_gpt4o_mini_transcribe_no_prompt():
    with patch("benchmark.transcription.whisper.AsyncOpenAI"):
        t = WhisperTranscriber(model="gpt-4o-mini-transcribe")
    assert t._effective_prompt() is None


def test_effective_prompt_custom_overrides_default():
    with patch("benchmark.transcription.whisper.AsyncOpenAI"):
        t = WhisperTranscriber(model="gpt-4o-transcribe", prompt="meu prompt")
    assert t._effective_prompt() == "meu prompt"


def test_effective_prompt_custom_overrides_none_model():
    with patch("benchmark.transcription.whisper.AsyncOpenAI"):
        t = WhisperTranscriber(model="whisper-1", prompt="meu prompt")
    assert t._effective_prompt() == "meu prompt"


# --- prompt passado à API ---

@patch("benchmark.transcription.whisper.AsyncOpenAI")
async def test_whisper1_no_prompt_not_sent(mock_openai_cls, audio_file):
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value=MagicMock(text="texto"))
    mock_openai_cls.return_value = mock_client

    transcriber = WhisperTranscriber(model="whisper-1")
    await transcriber.transcribe(audio_file)

    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert "prompt" not in call_kwargs


@patch("benchmark.transcription.whisper.AsyncOpenAI")
async def test_gpt4o_transcribe_uses_default_prompt(mock_openai_cls, audio_file):
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value=MagicMock(text="texto"))
    mock_openai_cls.return_value = mock_client

    transcriber = WhisperTranscriber(model="gpt-4o-transcribe")
    await transcriber.transcribe(audio_file)

    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs["prompt"] == DEFAULT_PROMPT_GPT4O_TRANSCRIBE


@patch("benchmark.transcription.whisper.AsyncOpenAI")
async def test_gpt4o_transcribe_custom_prompt_overrides_default(mock_openai_cls, audio_file):
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value=MagicMock(text="texto"))
    mock_openai_cls.return_value = mock_client

    transcriber = WhisperTranscriber(model="gpt-4o-transcribe", prompt="prompt customizado")
    await transcriber.transcribe(audio_file)

    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs["prompt"] == "prompt customizado"


@patch("benchmark.transcription.whisper.AsyncOpenAI")
async def test_gpt4o_mini_transcribe_no_prompt_not_sent(mock_openai_cls, audio_file):
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value=MagicMock(text="texto"))
    mock_openai_cls.return_value = mock_client

    transcriber = WhisperTranscriber(model="gpt-4o-mini-transcribe")
    await transcriber.transcribe(audio_file)

    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert "prompt" not in call_kwargs


@patch("benchmark.transcription.whisper.AsyncOpenAI")
async def test_transcribe_sends_neutral_filename(mock_openai_cls, tmp_path):
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value=MagicMock(text="x"))
    mock_openai_cls.return_value = mock_client
    named = tmp_path / "A Malandragem - Francisco Alves.mp3"
    named.write_bytes(b"fake audio content")

    await WhisperTranscriber(model="whisper-1").transcribe(named)

    name, data = mock_client.audio.transcriptions.create.call_args.kwargs["file"]
    assert name == "audio.mp3"
    assert data == b"fake audio content"


@patch("benchmark.transcription.whisper.AsyncOpenAI")
async def test_transcribe_records_usage(mock_openai_cls, audio_file):
    from openai.types.audio.transcription import UsageTokens

    usage = UsageTokens(type="tokens", input_tokens=500, output_tokens=120, total_tokens=620)
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="letra", usage=usage)
    )
    mock_openai_cls.return_value = mock_client

    transcriber = WhisperTranscriber(model="gpt-4o-transcribe")
    await transcriber.transcribe(audio_file)

    assert transcriber.last_usage["total_tokens"] == 620
    assert transcriber.last_usage["response_time_ms"] is not None
