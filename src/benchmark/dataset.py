import logging
from pathlib import Path

import frontmatter

from .models import SongData

logger = logging.getLogger("benchmark")


def load_dataset(dataset_path: str) -> list[SongData]:
    base = Path(dataset_path)
    if not base.exists():
        raise FileNotFoundError(f"Dataset path not found: {base}")

    songs: list[SongData] = []
    for song_dir in sorted(base.iterdir()):
        if not song_dir.is_dir():
            continue

        mp3_files = list(song_dir.glob("*.mp3"))
        gt_path = song_dir / "ground_truth.md"

        if len(mp3_files) == 0:
            logger.warning(f"No .mp3 file found in {song_dir.name}, skipping")
            continue
        if len(mp3_files) > 1:
            logger.warning(f"Multiple .mp3 files found in {song_dir.name}, skipping")
            continue
        audio_path = mp3_files[0]
        if not gt_path.exists():
            logger.warning(f"Missing ground_truth.md in {song_dir.name}, skipping")
            continue

        post = frontmatter.load(gt_path)
        songs.append(
            SongData(
                song_id=song_dir.name,
                titulo=post.get("titulo", ""),
                autoria=post.get("autoria", ""),
                interpretacao=post.get("interpretacao", ""),
                disco=post.get("disco", ""),
                ano=str(post.get("ano", "")),
                audio_path=audio_path,
                ground_truth=post.content.strip(),
            )
        )
        logger.debug(f"Loaded: {song_dir.name}")

    return songs
