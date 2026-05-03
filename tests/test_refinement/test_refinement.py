import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from benchmark.refinement import get_refiner
from benchmark.refinement.anthropic import AnthropicRefiner
from benchmark.refinement.base import PromptConfig, load_prompt
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


@patch("benchmark.refinement.openai.AsyncOpenAI")
async def test_openai_refiner(mock_cls, prompt):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="As rosas não falam"))]
    mock_response.usage = MagicMock(total_tokens=80)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_cls.return_value = mock_client

    refiner = OpenAIRefiner(model="gpt-4o")
    result = await refiner.refine("as rosas nao falam", prompt)

    assert result.refined_text == "As rosas não falam"
    assert result.tokens_used == 80
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o"


@patch("benchmark.refinement.anthropic.AsyncAnthropic")
async def test_anthropic_refiner(mock_cls, prompt):
    mock_client = MagicMock()
    mock_response = MagicMock()
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


def test_get_refiner_openai():
    with patch("benchmark.refinement.openai.AsyncOpenAI"):
        refiner = get_refiner("openai", "gpt-4o")
    assert isinstance(refiner, OpenAIRefiner)
    assert refiner.model == "gpt-4o"


def test_get_refiner_unknown_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_refiner("desconhecido", "modelo")
