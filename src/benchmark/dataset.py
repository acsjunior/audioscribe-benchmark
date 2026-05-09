import csv
from pathlib import Path

from slugify import slugify

from .models import SongData


def load_catalog(catalog_path: str | Path) -> list[SongData]:
    path = Path(catalog_path)
    if not path.exists():
        raise FileNotFoundError(f"Catálogo não encontrado: {catalog_path}")

    songs = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            titulo = row["Música"].strip()
            interpretacao = row["Interpretação"].strip()
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
            ))

    return sorted(songs, key=lambda s: s.song_id)
