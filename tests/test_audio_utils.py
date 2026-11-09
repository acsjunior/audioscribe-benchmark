from benchmark.audio_utils import anonymous_audio, strip_id3

FRAMES = b"\xff\xfb\x90\x00" + b"\x00" * 60


def _id3v2(payload: bytes) -> bytes:
    size = len(payload)
    syncsafe = bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F])
    return b"ID3\x03\x00\x00" + syncsafe + payload


def test_strip_id3_v2_and_v1():
    v1 = b"TAG" + b"A Malandragem".ljust(125, b"\x00")
    data = _id3v2(b"TIT2 A Malandragem - Francisco Alves") + FRAMES + v1
    assert strip_id3(data) == FRAMES


def test_strip_id3_without_tags_is_identity():
    assert strip_id3(FRAMES) == FRAMES


def test_anonymous_audio_uses_neutral_name(tmp_path):
    mp3 = tmp_path / "A Malandragem - Francisco Alves.mp3"
    mp3.write_bytes(_id3v2(b"titulo") + FRAMES)
    name, data = anonymous_audio(mp3)
    assert name == "audio.mp3"
    assert data == FRAMES

    wav = tmp_path / "Antonico_vocals.wav"
    wav.write_bytes(b"RIFF....")
    assert anonymous_audio(wav) == ("audio.wav", b"RIFF....")
