import logging
from pathlib import Path

logger = logging.getLogger("benchmark")

VOCALS_SUFFIX = "_vocals"
VOCALS_EXTENSION = ".wav"

try:
    from demucs.api import Separator
    import torchaudio
except ImportError:
    Separator = None  # type: ignore[assignment, misc]
    torchaudio = None  # type: ignore[assignment]


def isolated_voice_path(audio_path: Path) -> Path:
    return audio_path.parent / f"{audio_path.stem}{VOCALS_SUFFIX}{VOCALS_EXTENSION}"


def isolate_voice(audio_path: Path) -> Path:
    """Separate vocals from audio using demucs (htdemucs model).

    Returns the path to the isolated vocals WAV file.
    Uses a cached file if it already exists.
    """
    if Separator is None:
        raise ImportError(
            "demucs e torchaudio são necessários para isolamento de voz. "
            "Instale com: uv add demucs"
        )

    output_path = isolated_voice_path(audio_path)
    if output_path.exists():
        logger.debug(f"  Cache de voz isolada: {output_path.name}")
        return output_path

    logger.info(f"  Isolando voz: {audio_path.name} → {output_path.name}")
    separator = Separator(model="htdemucs")
    _, separated = separator.separate_audio_file(audio_path)
    vocals = separated["vocals"]
    torchaudio.save(str(output_path), vocals, separator.samplerate)
    logger.info(f"  Voz isolada salva: {output_path.name}")
    return output_path
