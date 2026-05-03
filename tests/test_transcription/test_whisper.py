from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from benchmark.transcription.whisper import WhisperTranscriber


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
