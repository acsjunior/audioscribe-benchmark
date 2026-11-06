import dataclasses
import logging
import sys
import types
from pathlib import Path

import soundfile as sf

logger = logging.getLogger("benchmark")

FILTERED_SUFFIX = "_deepfiltered"
FILTERED_EXTENSION = ".wav"


def _patch_torchaudio_for_deepfilternet() -> None:
    """Inject compatibility shim for deepfilternet with torchaudio >= 2.3.

    torchaudio 2.3+ removed torchaudio.backend.common.AudioMetaData and
    torchaudio.info(), which deepfilternet 0.5.x still imports at module level.
    """
    import torchaudio as ta

    @dataclasses.dataclass
    class AudioMetaData:
        sample_rate: int
        num_frames: int
        num_channels: int
        bits_per_sample: int
        encoding: str

    if "torchaudio.backend" not in sys.modules:
        backend_mod = types.ModuleType("torchaudio.backend")
        sys.modules["torchaudio.backend"] = backend_mod

    common_mod = types.ModuleType("torchaudio.backend.common")
    common_mod.AudioMetaData = AudioMetaData  # type: ignore[attr-defined]
    sys.modules["torchaudio.backend.common"] = common_mod

    if not hasattr(ta, "info"):
        def _info(path: str, **kwargs: object) -> AudioMetaData:
            info = sf.info(str(path))
            return AudioMetaData(
                sample_rate=info.samplerate,
                num_frames=info.frames,
                num_channels=info.channels,
                bits_per_sample=16,
                encoding="PCM_S",
            )
        ta.info = _info  # type: ignore[attr-defined]


try:
    _patch_torchaudio_for_deepfilternet()
    from df.enhance import enhance, init_df
    _deepfilternet_available = True
except Exception:
    enhance = None  # type: ignore[assignment]
    init_df = None  # type: ignore[assignment]
    _deepfilternet_available = False


def filtered_audio_path(audio_path: Path) -> Path:
    return audio_path.parent / f"{audio_path.stem}{FILTERED_SUFFIX}{FILTERED_EXTENSION}"


def filter_noise(audio_path: Path) -> Path:
    if not _deepfilternet_available:
        raise ImportError(
            "deepfilternet é necessário para filtragem de ruído. "
            "Instale com: uv add deepfilternet"
        )

    output_path = filtered_audio_path(audio_path)
    if output_path.exists():
        logger.debug(f"  Cache de áudio filtrado: {output_path.name}")
        return output_path

    logger.info(f"  Filtrando ruído (DeepFilterNet): {audio_path.name} → {output_path.name}")

    model, df_state, _ = init_df()

    # Use demucs.audio.AudioFile to decode MP3/WAV via ffmpeg — avoids the
    # TorchCodec dependency that torchaudio 2.x requires for MP3 loading.
    from demucs.audio import AudioFile
    audio = AudioFile(audio_path).read(streams=0, samplerate=df_state.sr(), channels=1)

    enhanced = enhance(model, df_state, audio)

    sf.write(str(output_path), enhanced.squeeze(0).cpu().numpy(), df_state.sr())

    logger.info(f"  Áudio filtrado salvo: {output_path.name}")
    return output_path
