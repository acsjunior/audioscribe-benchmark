import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from benchmark.refinement import get_refiner
from benchmark.refinement.anthropic import AnthropicRefiner
from benchmark.refinement.base import (
    BlockedResponseError,
    PromptConfig,
    TruncatedResponseError,
    load_prompt,
)
from benchmark.refinement.google import GoogleRefiner
from benchmark.refinement.openai import OpenAIRefiner


PROMPT_YAML = """\
name: minimalist
description: Correção mínima
system: "Você é um especialista em letras de música."
user: "Corrija: {transcription}"
"""


@pytest.fixture
def prompt() -> PromptConfig:
    return PromptConfig(
        name="minimalist",
        description="Correção mínima",
        system="Você é um especialista em letras de música.",
        user="Corrija: {transcription}",
        file="prompts/minimalist.yaml",
    )


def test_load_prompt(tmp_path):
    f = tmp_path / "minimalist.yaml"
    f.write_text(PROMPT_YAML, encoding="utf-8")
    p = load_prompt(str(f))
    assert p.name == "minimalist"
    assert p.format_user("texto") == "Corrija: texto"


def test_prompt_format_user(prompt):
    assert prompt.format_user("as rosas") == "Corrija: as rosas"


def test_prompt_format_user_with_metadata():
    p = PromptConfig(
        name="test",
        description="",
        system="sys",
        user="Música: {titulo}\nAno: {ano}\n{transcription}",
        file="test.yaml",
    )
    result = p.format_user("letra", {"titulo": "As Rosas Não Falam", "ano": "1976"})
    assert result == "Música: As Rosas Não Falam\nAno: 1976\nletra"


def test_prompt_format_user_missing_metadata_keys_become_empty():
    p = PromptConfig(
        name="test",
        description="",
        system="sys",
        user="Música: {titulo}\n{transcription}",
        file="test.yaml",
    )
    result = p.format_user("letra")
    assert result == "Música: \nletra"


# --- OpenAI ---

@patch("benchmark.refinement.openai.AsyncOpenAI")
async def test_openai_refiner(mock_cls, prompt):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(finish_reason="stop", message=MagicMock(content="As rosas não falam"))]
    mock_response.usage = MagicMock(total_tokens=80)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_cls.return_value = mock_client

    refiner = OpenAIRefiner(model="gpt-4o")
    result = await refiner.refine("as rosas nao falam", prompt)

    assert result.refined_text == "As rosas não falam"
    assert result.tokens_used == 80
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o"
    assert call_kwargs["temperature"] == 0.0
    assert call_kwargs["max_tokens"] == 4096


@patch("benchmark.refinement.openai.AsyncOpenAI")
async def test_openai_refiner_custom_temperature(mock_cls, prompt):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(finish_reason="stop", message=MagicMock(content="resultado"))]
    mock_response.usage = MagicMock(total_tokens=50)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_cls.return_value = mock_client

    refiner = OpenAIRefiner(model="gpt-4o", temperature=0.7)
    await refiner.refine("texto", prompt)

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["temperature"] == 0.7


@patch("benchmark.refinement.openai.AsyncOpenAI")
async def test_openai_refiner_passes_metadata(mock_cls):
    prompt_with_meta = PromptConfig(
        name="test",
        description="",
        system="sys",
        user="Música: {titulo}\nIntérprete: {interpretacao}\n{transcription}",
        file="test.yaml",
    )
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(finish_reason="stop", message=MagicMock(content="resultado"))]
    mock_response.usage = MagicMock(total_tokens=40)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_cls.return_value = mock_client

    refiner = OpenAIRefiner(model="gpt-4o")
    metadata = {"titulo": "As Rosas Não Falam", "interpretacao": "Cartola"}
    await refiner.refine("texto", prompt_with_meta, metadata)

    messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
    user_content = messages[-1]["content"]
    assert "As Rosas Não Falam" in user_content
    assert "Cartola" in user_content


# --- Anthropic ---

@patch("benchmark.refinement.anthropic.AsyncAnthropic")
async def test_anthropic_refiner(mock_cls, prompt):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [MagicMock(text="As rosas não falam")]
    mock_response.usage = MagicMock(input_tokens=50, output_tokens=30)
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    mock_cls.return_value = mock_client

    refiner = AnthropicRefiner(model="claude-opus-4-7")
    result = await refiner.refine("as rosas nao falam", prompt)

    assert result.refined_text == "As rosas não falam"
    assert result.tokens_used == 80
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-7"
    assert call_kwargs["system"] == prompt.system
    assert call_kwargs["temperature"] == 0.0


@patch("benchmark.refinement.anthropic.AsyncAnthropic")
async def test_anthropic_refiner_custom_temperature(mock_cls, prompt):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [MagicMock(text="resultado")]
    mock_response.usage = MagicMock(input_tokens=30, output_tokens=20)
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    mock_cls.return_value = mock_client

    refiner = AnthropicRefiner(model="claude-opus-4-7", temperature=0.5)
    await refiner.refine("texto", prompt)

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["temperature"] == 0.5


# --- Google ---

@patch("benchmark.refinement.google.genai.Client")
async def test_google_refiner(mock_client_cls, mocker, prompt):
    mock_client_cls.return_value = MagicMock()
    refiner = GoogleRefiner(model="gemini-2.0-flash")
    mocker.patch.object(
        refiner,
        "_call_sync",
        return_value=("As rosas não falam", 75, 400.0),
    )
    result = await refiner.refine("as rosas nao falam", prompt)

    assert result.refined_text == "As rosas não falam"
    assert result.tokens_used == 75
    assert result.response_time_ms == 400.0
    assert refiner.temperature == 0.0


@patch("benchmark.refinement.google.genai.Client")
async def test_google_refiner_custom_temperature(mock_client_cls, mocker, prompt):
    mock_client_cls.return_value = MagicMock()
    refiner = GoogleRefiner(model="gemini-2.0-flash", temperature=0.3)
    mocker.patch.object(refiner, "_call_sync", return_value=("resultado", 50, 200.0))
    await refiner.refine("texto", prompt)

    assert refiner.temperature == 0.3


# --- Registry ---

def test_get_refiner_openai():
    with patch("benchmark.refinement.openai.AsyncOpenAI"):
        refiner = get_refiner("openai", "gpt-4o")
    assert isinstance(refiner, OpenAIRefiner)
    assert refiner.model == "gpt-4o"
    assert refiner.temperature == 0.0


def test_get_refiner_openai_custom_temperature():
    with patch("benchmark.refinement.openai.AsyncOpenAI"):
        refiner = get_refiner("openai", "gpt-4o", temperature=0.8)
    assert refiner.temperature == 0.8


def test_get_refiner_unknown_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_refiner("desconhecido", "modelo")


# --- Truncamento ---

@patch("benchmark.refinement.openai.AsyncOpenAI")
async def test_openai_raises_on_truncation(mock_cls, prompt):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(finish_reason="length", message=MagicMock(content="parcial"))]
    mock_response.usage = MagicMock(total_tokens=80)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_cls.return_value = mock_client

    refiner = OpenAIRefiner(model="gpt-4o")
    with pytest.raises(TruncatedResponseError):
        await refiner.refine("texto", prompt)


@patch("benchmark.refinement.anthropic.AsyncAnthropic")
async def test_anthropic_raises_on_truncation(mock_cls, prompt):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.stop_reason = "max_tokens"
    mock_response.content = [MagicMock(text="parcial")]
    mock_response.usage = MagicMock(input_tokens=40, output_tokens=10)
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    mock_cls.return_value = mock_client

    refiner = AnthropicRefiner(model="claude-opus-4-7")
    with pytest.raises(TruncatedResponseError):
        await refiner.refine("texto", prompt)


@patch("benchmark.refinement.google.genai.Client")
async def test_google_raises_on_truncation(mock_client_cls, mocker, prompt):
    mock_client_cls.return_value = MagicMock()
    refiner = GoogleRefiner(model="gemini-2.0-flash")

    truncated_finish = MagicMock()
    truncated_finish.name = "MAX_TOKENS"
    mock_candidate = MagicMock(finish_reason=truncated_finish)
    mock_response = MagicMock(candidates=[mock_candidate])
    mock_response.usage_metadata = None

    mocker.patch.object(
        refiner.client.models,
        "generate_content",
        return_value=mock_response,
    )
    with pytest.raises(TruncatedResponseError):
        await refiner.refine("texto", prompt)


# --- Bloqueio (filtro de conteúdo / recitação) ---

@patch("benchmark.refinement.openai.AsyncOpenAI")
async def test_openai_raises_on_content_filter(mock_cls, prompt):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(finish_reason="content_filter", message=MagicMock(content="parcial"))
    ]
    mock_response.usage = MagicMock(total_tokens=80)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_cls.return_value = mock_client

    refiner = OpenAIRefiner(model="gpt-4o")
    with pytest.raises(BlockedResponseError):
        await refiner.refine("texto", prompt)


@patch("benchmark.refinement.anthropic.AsyncAnthropic")
async def test_anthropic_raises_on_refusal(mock_cls, prompt):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.stop_reason = "refusal"
    mock_response.content = [MagicMock(text="parcial")]
    mock_response.usage = MagicMock(input_tokens=40, output_tokens=10)
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    mock_cls.return_value = mock_client

    refiner = AnthropicRefiner(model="claude-opus-4-7")
    with pytest.raises(BlockedResponseError):
        await refiner.refine("texto", prompt)


@patch("benchmark.refinement.google.genai.Client")
async def test_google_raises_on_recitation(mock_client_cls, mocker, prompt):
    mock_client_cls.return_value = MagicMock()
    refiner = GoogleRefiner(model="gemini-2.0-flash")

    finish = MagicMock()
    finish.name = "RECITATION"
    mock_response = MagicMock(candidates=[MagicMock(finish_reason=finish)])
    mock_response.usage_metadata = None

    mocker.patch.object(refiner.client.models, "generate_content", return_value=mock_response)
    with pytest.raises(BlockedResponseError):
        await refiner.refine("texto", prompt)
