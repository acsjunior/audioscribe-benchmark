import json

from benchmark.transcription.cache import TranscriptionCache, file_sha256, transcription_key


def _cache(tmp_path, model="gpt-4o-transcribe", prompt="ctx", pre=None):
    return TranscriptionCache(tmp_path / "cache", model=model, prompt=prompt, preprocessing=pre)


def test_key_changes_with_each_parameter():
    base = transcription_key("gpt-4o-transcribe", "ctx", None)
    assert transcription_key("whisper-1", "ctx", None) != base
    assert transcription_key("gpt-4o-transcribe", "outro", None) != base
    assert transcription_key("gpt-4o-transcribe", "ctx", "demucs") != base
    assert transcription_key("gpt-4o-transcribe", "ctx", None) == base


def test_key_without_prompt():
    assert transcription_key("whisper-1", None, None) == "whisper-1__original__noprompt"


def test_save_and_load_roundtrip(tmp_path):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"audio")
    sha = file_sha256(audio)
    cache = _cache(tmp_path)

    assert cache.load("song", 1, sha) is None
    cache.save("song", 1, "texto", audio, sha)

    assert cache.load("song", 1, sha) == "texto"
    assert cache.load("song", 2, sha) is None


def test_saved_record_and_manifest(tmp_path):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"audio")
    sha = file_sha256(audio)
    cache = _cache(tmp_path, pre="demucs")
    cache.save("song", 3, "texto", audio, sha)

    record = json.loads((cache.dir / "song" / "run_03.json").read_text(encoding="utf-8"))
    assert record["run"] == 3
    assert record["audio_sha256"] == sha
    assert record["audio_preprocessing"] == "demucs"
    assert "created_at" in record

    manifest = json.loads((cache.dir / "config.json").read_text(encoding="utf-8"))
    assert manifest == {
        "model": "gpt-4o-transcribe",
        "prompt": "ctx",
        "audio_preprocessing": "demucs",
    }


def test_load_ignores_entry_when_audio_changed(tmp_path):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"audio")
    cache = _cache(tmp_path)
    cache.save("song", 1, "texto", audio, file_sha256(audio))

    audio.write_bytes(b"outro audio")
    assert cache.load("song", 1, file_sha256(audio)) is None


def test_usage_is_saved_with_the_entry(tmp_path):
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"audio")
    sha = file_sha256(audio)
    cache = _cache(tmp_path)
    cache.save("song", 1, "texto", audio, sha, usage={"total_tokens": 620})
    cache.save("song", 2, "texto", audio, sha)

    assert cache.load_entry("song", 1, sha)["usage"] == {"total_tokens": 620}
    assert cache.load_entry("song", 2, sha)["usage"] is None
    assert cache.load_entry("song", 1, "outro-sha") is None
