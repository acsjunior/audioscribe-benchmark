from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from benchmark.voice_isolation import isolated_voice_path, isolate_voice


def test_isolated_voice_path_mp3(tmp_path):
    audio = tmp_path / "samba.mp3"
    result = isolated_voice_path(audio)
    assert result == tmp_path / "samba_vocals.wav"


def test_isolated_voice_path_wav(tmp_path):
    audio = tmp_path / "track.wav"
    result = isolated_voice_path(audio)
    assert result == tmp_path / "track_vocals.wav"


def test_isolate_voice_uses_cache(tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")
    cached = tmp_path / "samba_vocals.wav"
    cached.write_bytes(b"cached vocals")

    with patch("benchmark.voice_isolation._demucs_available", True):
        result = isolate_voice(audio)

    assert result == cached


@patch("benchmark.voice_isolation.sf")
@patch("benchmark.voice_isolation.apply_model")
@patch("benchmark.voice_isolation.AudioFile")
@patch("benchmark.voice_isolation.get_model")
@patch("benchmark.voice_isolation.torch")
def test_isolate_voice_calls_demucs(mock_torch, mock_get_model, mock_audio_file, mock_apply_model, mock_sf, tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")

    mock_model = MagicMock()
    mock_model.samplerate = 44100
    mock_model.audio_channels = 2
    mock_model.sources = ["drums", "bass", "other", "vocals"]
    mock_get_model.return_value = mock_model

    mock_wav = MagicMock()
    mock_audio_file.return_value.read.return_value = mock_wav

    mock_vocals = MagicMock()
    mock_vocals.shape = (1, 44100)
    mock_sources = MagicMock()
    mock_sources.__getitem__ = MagicMock(return_value=mock_vocals)
    mock_apply_model.return_value = [mock_sources]

    with patch("benchmark.voice_isolation._demucs_available", True):
        result = isolate_voice(audio)

    mock_get_model.assert_called_once_with(name="htdemucs")
    mock_audio_file.assert_called_once_with(audio)
    mock_apply_model.assert_called_once()
    mock_sf.write.assert_called_once()
    assert result == tmp_path / "samba_vocals.wav"


@patch("benchmark.voice_isolation.sf")
@patch("benchmark.voice_isolation.apply_model")
@patch("benchmark.voice_isolation.AudioFile")
@patch("benchmark.voice_isolation.get_model")
@patch("benchmark.voice_isolation.torch")
def test_isolate_voice_does_not_reprocess_if_cached(mock_torch, mock_get_model, mock_audio_file, mock_apply_model, mock_sf, tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")
    cached = tmp_path / "samba_vocals.wav"
    cached.write_bytes(b"cached")

    with patch("benchmark.voice_isolation._demucs_available", True):
        isolate_voice(audio)

    mock_get_model.assert_not_called()
    mock_sf.write.assert_not_called()


def test_isolate_voice_raises_clear_error_without_demucs(tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")

    with patch("benchmark.voice_isolation._demucs_available", False):
        with pytest.raises(ImportError, match="demucs"):
            isolate_voice(audio)
