from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from benchmark.verification.edits import EditParseError
from benchmark.verification.verifier import (
    AUDIO_NOTE_WITH_AUDIO,
    AUDIO_NOTE_WITHOUT_AUDIO,
    Verifier,
    format_metadata,
    load_verification_prompt,
)

PROMPT_FILE = "prompts/verification/edits_v1.yaml"
DRAFT = "ele está dançando na porta-bamba, toca cuíca, toca sulto e tamborim"


@pytest.fixture
def verifier():
    with patch("benchmark.verification.verifier.get_audio_llm") as get_llm:
        llm = MagicMock()
        llm.complete = AsyncMock(return_value='{"edits": []}')
        get_llm.return_value = llm
        yield Verifier("openai-audio", "gpt-audio", load_verification_prompt(PROMPT_FILE))


def test_prompt_file_has_all_placeholders():
    prompt = load_verification_prompt(PROMPT_FILE)
    for placeholder in ("{segments}", "{metadata}", "{audio_note}"):
        assert placeholder in prompt.user


def test_format_metadata():
    assert format_metadata(None) == ""
    out = format_metadata({"titulo": "Antonico", "autoria": "Ismael Silva", "ano": ""})
    assert "Título: Antonico" in out
    assert "Autoria: Ismael Silva" in out
    assert "Ano" not in out


def test_user_message_variants(verifier):
    with_audio = verifier.build_user_message(["a b"], True, {"titulo": "Antonico"})
    assert AUDIO_NOTE_WITH_AUDIO in with_audio
    assert "[1] a b" in with_audio
    assert "Título: Antonico" in with_audio
    assert '{"edits": []}' in with_audio  # chaves do JSON do prompt preservadas

    text_only = verifier.build_user_message(["a b"], False, None)
    assert AUDIO_NOTE_WITHOUT_AUDIO in text_only
    assert "Título" not in text_only
    assert "{" + "metadata}" not in text_only


async def test_verify_applies_edits(verifier, tmp_path):
    verifier.llm.complete.return_value = (
        '{"edits": [{"op": "replace", "segment": 1, "old": "porta-bamba", "new": "corda bamba"}]}'
    )
    audio = tmp_path / "a.mp3"
    out = await verifier.verify(DRAFT, audio, None)

    assert "corda bamba" in out.text
    assert out.num_applied == 1
    args, kwargs = verifier.llm.complete.call_args
    assert args[1] == audio
    assert kwargs["system"] == verifier.prompt.system


async def test_verify_without_audio_and_no_edits(verifier):
    out = await verifier.verify(DRAFT, None, None)
    assert out.text == DRAFT
    assert out.outcomes == []
    assert verifier.llm.complete.call_args.args[1] is None


async def test_verify_malformed_response_raises(verifier):
    verifier.llm.complete.return_value = "Está tudo certo."
    with pytest.raises(EditParseError):
        await verifier.verify(DRAFT, None, None)


async def test_verify_carries_the_call_usage(verifier):
    verifier.llm.last_usage = {"total_tokens": 900, "response_time_ms": 1500}
    out = await verifier.verify(DRAFT, None)
    assert out.usage == {"total_tokens": 900, "response_time_ms": 1500}


async def test_verify_without_usage(verifier):
    out = await verifier.verify(DRAFT, None)  # dublê sem registro de uso
    assert out.usage is None
