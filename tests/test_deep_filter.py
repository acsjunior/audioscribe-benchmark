from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch

from benchmark.deep_filter import filter_noise, filtered_audio_path


def test_filtered_audio_path_mp3(tmp_path):
    audio = tmp_path / "samba.mp3"
    result = filtered_audio_path(audio)
    assert result == tmp_path / "samba_deepfiltered.wav"


def test_filtered_audio_path_wav(tmp_path):
    audio = tmp_path / "track.wav"
    result = filtered_audio_path(audio)
    assert result == tmp_path / "track_deepfiltered.wav"


def test_filter_noise_uses_cache(tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")
    cached = tmp_path / "samba_deepfiltered.wav"
    cached.write_bytes(b"cached")

    with patch("benchmark.deep_filter._deepfilternet_available", True):
        result = filter_noise(audio)

    assert result == cached


@patch("benchmark.deep_filter.sf")
@patch("benchmark.deep_filter.enhance")
@patch("benchmark.deep_filter.init_df")
@patch("demucs.audio.AudioFile")
def test_filter_noise_processes_audio(mock_audio_file_cls, mock_init_df, mock_enhance, mock_sf, tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")

    mock_df_state = MagicMock()
    mock_df_state.sr.return_value = 48000
    mock_init_df.return_value = (MagicMock(), mock_df_state, None)

    fake_wav = torch.zeros(1, 1000)
    mock_audio_file_cls.return_value.read.return_value = fake_wav
    mock_enhance.return_value = fake_wav

    with patch("benchmark.deep_filter._deepfilternet_available", True):
        result = filter_noise(audio)

    mock_init_df.assert_called_once()
    mock_audio_file_cls.assert_called_once()
    mock_enhance.assert_called_once()
    mock_sf.write.assert_called_once()
    assert result == tmp_path / "samba_deepfiltered.wav"


@patch("benchmark.deep_filter.sf")
@patch("benchmark.deep_filter.enhance")
@patch("benchmark.deep_filter.init_df")
@patch("demucs.audio.AudioFile")
def test_filter_noise_does_not_reprocess_if_cached(mock_audio_file_cls, mock_init_df, mock_enhance, mock_sf, tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")
    cached = tmp_path / "samba_deepfiltered.wav"
    cached.write_bytes(b"cached")

    with patch("benchmark.deep_filter._deepfilternet_available", True):
        filter_noise(audio)

    mock_init_df.assert_not_called()
    mock_audio_file_cls.assert_not_called()
    mock_enhance.assert_not_called()
    mock_sf.write.assert_not_called()


def test_filter_noise_raises_clear_error_without_deepfilternet(tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")

    with patch("benchmark.deep_filter._deepfilternet_available", False):
        with pytest.raises(ImportError, match="deepfilternet"):
            filter_noise(audio)
