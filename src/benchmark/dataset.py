import csv
import logging
from pathlib import Path

from slugify import slugify

from .models import SongData

logger = logging.getLogger("benchmark")

SPLIT_COLUMN = "Split"
VALID_SPLITS = {"dev", "test"}


def load_catalog(catalog_path: str | Path) -> list[SongData]:
    path = Path(catalog_path)
    if not path.exists():
        raise FileNotFoundError(f"Catálogo não encontrado: {catalog_path}")

    songs = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        has_split = SPLIT_COLUMN in (reader.fieldnames or [])
        if not has_split:
            logger.warning(
                f"Catálogo sem coluna '{SPLIT_COLUMN}': todas as músicas tratadas como 'dev'."
            )

        for row in reader:
            titulo = row["Música"].strip()
            interpretacao = row["Interpretação"].strip()

            split = "dev"
            if has_split:
                split = (row[SPLIT_COLUMN] or "").strip().lower()
                if split not in VALID_SPLITS:
                    raise ValueError(
                        f"Valor inválido na coluna '{SPLIT_COLUMN}' para "
                        f"'{titulo}' ({interpretacao}): '{split}'. Use 'dev' ou 'test'."
                    )

            songs.append(SongData(
                song_id=f"{slugify(interpretacao)}-{slugify(titulo)}",
                titulo=titulo,
                autoria=row["Autoria"].strip(),
                interpretacao=interpretacao,
                disco=row["Disco"].strip(),
                ano=row["Ano"].strip(),
                genero=row["Gênero"].strip(),
                audio_url=row["URL"].strip(),
                audio_filename=row["Arquivo"].strip(),
                ground_truth=row["Letra"].strip(),
                split=split,
            ))

    return sorted(songs, key=lambda s: s.song_id)
