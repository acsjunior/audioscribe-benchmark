import logging
from pathlib import Path

from .models import SongData

logger = logging.getLogger("benchmark")

_SEPARATOR = "---"


def _parse_ground_truth(path: Path) -> tuple[dict[str, str], str]:
    content = path.read_text(encoding="utf-8")
    if _SEPARATOR not in content:
        return {}, content.strip()

    header_part, lyrics_part = content.split(_SEPARATOR, 1)
    metadata: dict[str, str] = {}
    for line in header_part.strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()

    return metadata, lyrics_part.strip()


def load_dataset(dataset_path: str) -> list[SongData]:
    base = Path(dataset_path)
    if not base.exists():
        raise FileNotFoundError(f"Dataset path not found: {base}")

    songs: list[SongData] = []
    for song_dir in sorted(base.iterdir()):
        if not song_dir.is_dir():
            continue

        audio_path = song_dir / "audio.mp3"
        gt_path = song_dir / "ground_truth.txt"

        if not audio_path.exists():
            logger.warning(f"Missing audio.mp3 in {song_dir.name}, skipping")
            continue
        if not gt_path.exists():
            logger.warning(f"Missing ground_truth.txt in {song_dir.name}, skipping")
            continue

        metadata, lyrics = _parse_ground_truth(gt_path)
        songs.append(
            SongData(
                song_id=song_dir.name,
                artista=metadata.get("artista", ""),
                titulo=metadata.get("titulo", ""),
                ano=metadata.get("ano", ""),
                album=metadata.get("album", ""),
                audio_path=audio_path,
                ground_truth=lyrics,
            )
        )
        logger.debug(f"Loaded: {song_dir.name}")

    return songs
