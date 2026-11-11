"""Cache em disco das transcrições, por configuração de transcrição e rodada.

Estrutura:
    <root>/<chave>/config.json              descrição completa da configuração
    <root>/<chave>/<song_id>/run_01.json    uma transcrição por rodada

A chave combina modelo, pré-processamento e hash do prompt efetivo, de modo que
qualquer mudança nesses parâmetros gera um conjunto novo de transcrições.
"""

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from slugify import slugify

logger = logging.getLogger("benchmark")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def transcription_key(model: str, prompt: str | None, preprocessing: str | None) -> str:
    prompt_part = (
        "p" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8] if prompt else "noprompt"
    )
    return f"{slugify(model)}__{preprocessing or 'original'}__{prompt_part}"


class TranscriptionCache:
    def __init__(
        self, root: Path, model: str, prompt: str | None, preprocessing: str | None
    ) -> None:
        self.model = model
        self.prompt = prompt
        self.preprocessing = preprocessing
        self.key = transcription_key(model, prompt, preprocessing)
        self.dir = Path(root) / self.key

    def _path(self, song_id: str, run: int) -> Path:
        return self.dir / song_id / f"run_{run:02d}.json"

    def _write_manifest(self) -> None:
        manifest = self.dir / "config.json"
        if manifest.exists():
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "model": self.model,
                    "prompt": self.prompt,
                    "audio_preprocessing": self.preprocessing,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def load_entry(self, song_id: str, run: int, audio_sha256: str) -> dict | None:
        """Entrada completa da rodada (texto, uso da chamada original...), ou None."""
        path = self._path(song_id, run)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("audio_sha256") != audio_sha256:
            logger.warning(
                f"  Cache ignorado ({song_id}, rodada {run}): o arquivo de áudio mudou"
            )
            return None
        return data

    def load(self, song_id: str, run: int, audio_sha256: str) -> str | None:
        entry = self.load_entry(song_id, run, audio_sha256)
        return entry["text"] if entry is not None else None

    def save(
        self,
        song_id: str,
        run: int,
        text: str,
        audio_path: Path,
        audio_sha256: str,
        usage: dict | None = None,
    ) -> None:
        self._write_manifest()
        path = self._path(song_id, run)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "song_id": song_id,
                    "run": run,
                    "text": text,
                    "model": self.model,
                    "prompt": self.prompt,
                    "audio_preprocessing": self.preprocessing,
                    "audio_file": audio_path.name,
                    "audio_sha256": audio_sha256,
                    "usage": usage,
                    "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
