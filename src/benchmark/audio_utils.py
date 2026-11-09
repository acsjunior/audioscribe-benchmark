"""Áudio enviado aos modelos sem nada que identifique a música.

O nome do arquivo (``Música - Intérprete.mp3``) e as tags ID3 podem dizer ao modelo
qual música está sendo transcrita, o que permitiria acertar por memorização da letra
em vez de ouvir. Por isso todo áudio sai daqui:

- com nome neutro (``audio.mp3`` / ``audio.wav``) — a API de transcrição recebe o nome
  do arquivo no upload;
- sem tags ID3v2 (início do arquivo) nem ID3v1 (últimos 128 bytes) no MP3.

Metadados só chegam ao modelo quando um experimento os pede explicitamente no prompt
(``verification[].metadata: true``).
"""

from pathlib import Path

NEUTRAL_STEM = "audio"


def strip_id3(data: bytes) -> bytes:
    """Remove as tags ID3v2 (pode haver mais de uma) e ID3v1 de um MP3."""
    while len(data) >= 10 and data[:3] == b"ID3":
        flags = data[5]
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        total = 10 + size + (10 if flags & 0x10 else 0)  # rodapé opcional
        data = data[total:]
    if len(data) >= 128 and data[-128:-125] == b"TAG":
        data = data[:-128]
    return data


def anonymous_audio(audio_path: Path) -> tuple[str, bytes]:
    """Nome neutro e conteúdo sem tags, prontos para enviar a uma API."""
    suffix = audio_path.suffix.lower()
    data = audio_path.read_bytes()
    if suffix == ".mp3":
        data = strip_id3(data)
    return f"{NEUTRAL_STEM}{suffix}", data
