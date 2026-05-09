import logging
from pathlib import Path

logger = logging.getLogger("benchmark")

VOCALS_SUFFIX = "_vocals"
VOCALS_EXTENSION = ".wav"

try:
    import torch
    import torchaudio
    from demucs.apply import apply_model
    from demucs.pretrained import get_model
    _demucs_available = True
except ImportError:
    torch = None  # type: ignore[assignment]
    torchaudio = None  # type: ignore[assignment]
    apply_model = None  # type: ignore[assignment]
    get_model = None  # type: ignore[assignment]
    _demucs_available = False


def isolated_voice_path(audio_path: Path) -> Path:
    return audio_path.parent / f"{audio_path.stem}{VOCALS_SUFFIX}{VOCALS_EXTENSION}"


def isolate_voice(audio_path: Path) -> Path:
    """Separate vocals from audio using demucs (htdemucs model).

    Returns the path to the isolated vocals WAV file.
    Uses a cached file if it already exists.
    """
    if not _demucs_available:
        raise ImportError(
            "demucs e torchaudio são necessários para isolamento de voz. "
            "Instale com: uv add demucs"
        )

    output_path = isolated_voice_path(audio_path)
    if output_path.exists():
        logger.debug(f"  Cache de voz isolada: {output_path.name}")
        return output_path

    logger.info(f"  Isolando voz: {audio_path.name} → {output_path.name}")

    model = get_model("htdemucs")
    model.eval()

    wav, sr = torchaudio.load(str(audio_path))

    # Ensure stereo
    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)
    elif wav.shape[0] > 2:
        wav = wav[:2]

    # Resample if needed
    if sr != model.samplerate:
        wav = torchaudio.functional.resample(wav, sr, model.samplerate)

    # Normalize
    ref = wav.mean(0)
    wav = (wav - ref.mean()) / (ref.std() + 1e-8)

    with torch.no_grad():
        sources = apply_model(model, wav.unsqueeze(0))

    vocals_idx = list(model.sources).index("vocals")
    vocals = sources[0, vocals_idx]
    vocals = vocals * (ref.std() + 1e-8) + ref.mean()

    torchaudio.save(str(output_path), vocals.cpu(), model.samplerate)
    logger.info(f"  Voz isolada salva: {output_path.name}")
    return output_path
