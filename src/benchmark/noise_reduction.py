import logging
from pathlib import Path

import soundfile as sf

logger = logging.getLogger("benchmark")

DENOISED_SUFFIX = "_denoised"
DENOISED_EXTENSION = ".wav"

try:
    import noisereduce as nr
    _noisereduce_available = True
except ImportError:
    nr = None  # type: ignore[assignment]
    _noisereduce_available = False


def denoised_audio_path(audio_path: Path) -> Path:
    return audio_path.parent / f"{audio_path.stem}{DENOISED_SUFFIX}{DENOISED_EXTENSION}"


def reduce_noise(audio_path: Path) -> Path:
    """Reduce stationary noise from audio using noisereduce.

    Returns the path to the denoised WAV file.
    Uses a cached file if it already exists.
    """
    if not _noisereduce_available:
        raise ImportError(
            "noisereduce é necessário para redução de ruído. "
            "Instale com: uv add noisereduce"
        )

    output_path = denoised_audio_path(audio_path)
    if output_path.exists():
        logger.debug(f"  Cache de áudio sem ruído: {output_path.name}")
        return output_path

    logger.info(f"  Reduzindo ruído: {audio_path.name} → {output_path.name}")

    data, rate = sf.read(str(audio_path))

    # soundfile returns (samples,) for mono or (samples, channels) for stereo.
    # noisereduce expects (channels, samples) for multi-channel.
    if data.ndim == 2:
        reduced = nr.reduce_noise(y=data.T, sr=rate, stationary=True)
        reduced = reduced.T
    else:
        reduced = nr.reduce_noise(y=data, sr=rate, stationary=True)

    sf.write(str(output_path), reduced, rate)
    logger.info(f"  Áudio sem ruído salvo: {output_path.name}")
    return output_path
