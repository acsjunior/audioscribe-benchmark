from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from benchmark.refinement.base import BlockedResponseError, TruncatedResponseError
from benchmark.transcription.multimodal import (
    DEFAULT_MULTIMODAL_PROMPT,
    GeminiTranscriber,
    OpenAIAudioTranscriber,
    get_multimodal_transcriber,
    multimodal_prompt,
)


@pytest.fixture
def audio(tmp_path):
    p = tmp_path / "a.mp3"
    p.write_bytes(b"fake-audio")
    return p


def _finish(name):
    f = MagicMock()
    f.name = name
    return f


def _gemini_response(text="  letra cantada  ", finish="STOP"):
    r = MagicMock(candidates=[MagicMock(finish_reason=_finish(finish))])
    r.text = text
    return r


def test_default_prompt_is_neutral():
    assert multimodal_prompt(None) == DEFAULT_MULTIMODAL_PROMPT
    assert multimodal_prompt("meu prompt") == "meu prompt"
    # controle: não pode trazer metadados que permitam acertar por memorização
    for word in ("título", "autoria", "intérprete"):
        assert word not in DEFAULT_MULTIMODAL_PROMPT.lower().replace("títulos", "")


@patch("benchmark.transcription.multimodal.genai.Client")
async def test_gemini_transcribes_audio_inline(mock_client_cls, audio):
    client = MagicMock()
    client.models.generate_content.return_value = _gemini_response()
    mock_client_cls.return_value = client

    text = await GeminiTranscriber(model="gemini-2.5-flash").transcribe(audio)

    assert text == "letra cantada"
    kwargs = client.models.generate_content.call_args.kwargs
    parts = kwargs["contents"][0].parts
    assert parts[0].text == DEFAULT_MULTIMODAL_PROMPT
    assert parts[1].inline_data.data == b"fake-audio"
    assert parts[1].inline_data.mime_type == "audio/mpeg"
    assert kwargs["config"].temperature == 0.0


@pytest.mark.parametrize("reason", ["RECITATION", "SAFETY"])
@patch("benchmark.transcription.multimodal.genai.Client")
async def test_gemini_blocked(mock_client_cls, audio, reason):
    client = MagicMock()
    client.models.generate_content.return_value = _gemini_response("parcial", reason)
    mock_client_cls.return_value = client
    with pytest.raises(BlockedResponseError):
        await GeminiTranscriber().transcribe(audio)


@patch("benchmark.transcription.multimodal.genai.Client")
async def test_gemini_truncated_and_empty(mock_client_cls, audio):
    client = MagicMock()
    mock_client_cls.return_value = client
    client.models.generate_content.return_value = _gemini_response("x", "MAX_TOKENS")
    with pytest.raises(TruncatedResponseError):
        await GeminiTranscriber().transcribe(audio)
    client.models.generate_content.return_value = _gemini_response(None)
    with pytest.raises(RuntimeError, match="vazia"):
        await GeminiTranscriber().transcribe(audio)


async def test_unsupported_audio_format(tmp_path):
    flac = tmp_path / "a.flac"
    flac.write_bytes(b"x")
    with patch("benchmark.transcription.multimodal.genai.Client"):
        with pytest.raises(ValueError, match="não suportado"):
            await GeminiTranscriber().transcribe(flac)


def _openai_response(content="  letra  \nverso dois  ", finish="stop"):
    r = MagicMock()
    r.choices = [MagicMock(finish_reason=finish, message=MagicMock(content=content))]
    return r


@patch("benchmark.transcription.multimodal.AsyncOpenAI")
async def test_openai_audio_sends_input_audio(mock_cls, audio):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_openai_response())
    mock_cls.return_value = client

    text = await OpenAIAudioTranscriber(model="gpt-audio").transcribe(audio)

    assert text == "letra\nverso dois"
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["modalities"] == ["text"]
    content = kwargs["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": DEFAULT_MULTIMODAL_PROMPT}
    assert content[1]["input_audio"]["format"] == "mp3"
    assert content[1]["input_audio"]["data"] == "ZmFrZS1hdWRpbw=="


@pytest.mark.parametrize(
    ("finish", "error"),
    [("content_filter", BlockedResponseError), ("length", TruncatedResponseError)],
)
@patch("benchmark.transcription.multimodal.AsyncOpenAI")
async def test_openai_audio_incomplete_responses(mock_cls, audio, finish, error):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_openai_response("x", finish))
    mock_cls.return_value = client
    with pytest.raises(error):
        await OpenAIAudioTranscriber().transcribe(audio)


def test_registry_unknown_provider():
    with pytest.raises(ValueError, match="desconhecido"):
        get_multimodal_transcriber("anthropic", "x")
