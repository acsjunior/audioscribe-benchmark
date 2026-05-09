from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from benchmark.noise_reduction import denoised_audio_path, reduce_noise


def test_denoised_audio_path_mp3(tmp_path):
    audio = tmp_path / "samba.mp3"
    result = denoised_audio_path(audio)
    assert result == tmp_path / "samba_denoised.wav"


def test_denoised_audio_path_wav(tmp_path):
    audio = tmp_path / "track.wav"
    result = denoised_audio_path(audio)
    assert result == tmp_path / "track_denoised.wav"


def test_reduce_noise_uses_cache(tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")
    cached = tmp_path / "samba_denoised.wav"
    cached.write_bytes(b"cached")

    with patch("benchmark.noise_reduction._noisereduce_available", True):
        result = reduce_noise(audio)

    assert result == cached


@patch("benchmark.noise_reduction.sf")
@patch("benchmark.noise_reduction.nr")
def test_reduce_noise_mono(mock_nr, mock_sf, tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")

    mono_data = np.zeros(44100)
    mock_sf.read.return_value = (mono_data, 44100)
    mock_nr.reduce_noise.return_value = mono_data

    with patch("benchmark.noise_reduction._noisereduce_available", True):
        result = reduce_noise(audio)

    mock_nr.reduce_noise.assert_called_once()
    call_kwargs = mock_nr.reduce_noise.call_args.kwargs
    assert call_kwargs["sr"] == 44100
    assert call_kwargs["stationary"] is True
    mock_sf.write.assert_called_once()
    assert result == tmp_path / "samba_denoised.wav"


@patch("benchmark.noise_reduction.sf")
@patch("benchmark.noise_reduction.nr")
def test_reduce_noise_stereo_transposes(mock_nr, mock_sf, tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")

    stereo_data = np.zeros((44100, 2))  # (samples, channels) — formato soundfile
    mock_sf.read.return_value = (stereo_data, 44100)
    mock_nr.reduce_noise.return_value = stereo_data.T  # (channels, samples)

    with patch("benchmark.noise_reduction._noisereduce_available", True):
        reduce_noise(audio)

    # verifica que noisereduce recebeu (channels, samples)
    call_y = mock_nr.reduce_noise.call_args.kwargs["y"]
    assert call_y.shape == (2, 44100)

    # verifica que sf.write recebeu (samples, channels)
    saved_data = mock_sf.write.call_args.args[1]
    assert saved_data.shape == (44100, 2)


@patch("benchmark.noise_reduction.sf")
@patch("benchmark.noise_reduction.nr")
def test_reduce_noise_does_not_reprocess_if_cached(mock_nr, mock_sf, tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")
    cached = tmp_path / "samba_denoised.wav"
    cached.write_bytes(b"cached")

    with patch("benchmark.noise_reduction._noisereduce_available", True):
        reduce_noise(audio)

    mock_nr.reduce_noise.assert_not_called()
    mock_sf.write.assert_not_called()


def test_reduce_noise_raises_clear_error_without_noisereduce(tmp_path):
    audio = tmp_path / "samba.mp3"
    audio.write_bytes(b"fake")

    with patch("benchmark.noise_reduction._noisereduce_available", False):
        with pytest.raises(ImportError, match="noisereduce"):
            reduce_noise(audio)
