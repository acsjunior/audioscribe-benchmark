import logging
from pathlib import Path

logger = logging.getLogger("benchmark")

VOCALS_SUFFIX = "_vocals"
VOCALS_EXTENSION = ".wav"

try:
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.audio import AudioFile
    from demucs.pretrained import get_model
    _demucs_available = True
except ImportError:
    sf = None  # type: ignore[assignment]
    torch = None  # type: ignore[assignment]
    apply_model = None  # type: ignore[assignment]
    AudioFile = None  # type: ignore[assignment]
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
            "demucs, torchaudio e soundfile são necessários para isolamento de voz. "
            "Instale com: uv add demucs soundfile"
        )

    output_path = isolated_voice_path(audio_path)
    if output_path.exists():
        logger.debug(f"  Cache de voz isolada: {output_path.name}")
        return output_path

    logger.info(f"  Isolando voz: {audio_path.name} → {output_path.name}")

    model = get_model(name="htdemucs")
    model.to("cpu")

    wav = AudioFile(audio_path).read(
        streams=0,
        samplerate=model.samplerate,
        channels=model.audio_channels,
    )

    with torch.no_grad():
        sources = apply_model(model, wav[None], device="cpu")[0]

    vocals = sources[model.sources.index("vocals")]

    if vocals.shape[0] > 1:
        vocals = torch.mean(vocals, dim=0, keepdim=True)

    sf.write(str(output_path), vocals.T.cpu().numpy(), samplerate=model.samplerate)
    logger.info(f"  Voz isolada salva: {output_path.name}")
    return output_path
