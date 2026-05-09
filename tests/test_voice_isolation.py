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

    with patch("benchmark.voice_isolation.Separator", MagicMock()):
        result = isolate_voice(audio)

    assert result == cached


@patch("benchmark.voice_isolation.torchaudio")
@patch("benchmark.voice_isolation.Separator")
def test_isolate_voice_calls_demucs(mock_separator_cls, mock_torchaudio, tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")

    mock_separator = MagicMock()
    mock_separator.samplerate = 44100
    mock_vocals = MagicMock()
    mock_separator.separate_audio_file.return_value = (MagicMock(), {"vocals": mock_vocals})
    mock_separator_cls.return_value = mock_separator

    result = isolate_voice(audio)

    mock_separator_cls.assert_called_once_with(model="htdemucs")
    mock_separator.separate_audio_file.assert_called_once_with(audio)
    mock_torchaudio.save.assert_called_once()

    saved_path = mock_torchaudio.save.call_args.args[0]
    assert saved_path.endswith("samba_vocals.wav")
    assert result == tmp_path / "samba_vocals.wav"


@patch("benchmark.voice_isolation.torchaudio")
@patch("benchmark.voice_isolation.Separator")
def test_isolate_voice_does_not_reprocess_if_cached(mock_separator_cls, mock_torchaudio, tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")
    cached = tmp_path / "samba_vocals.wav"
    cached.write_bytes(b"cached")

    isolate_voice(audio)

    mock_separator_cls.assert_not_called()
    mock_torchaudio.save.assert_not_called()


def test_isolate_voice_raises_clear_error_without_demucs(tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")

    with patch("benchmark.voice_isolation.Separator", None):
        with pytest.raises(ImportError, match="demucs"):
            isolate_voice(audio)
