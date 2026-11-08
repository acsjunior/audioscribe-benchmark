import pytest
import yaml

from benchmark.config import load_config
from benchmark.config.schema import ExperimentConfig, RefinementConfig


MINIMAL_YAML = """
experiment_name: teste
metrics:
  - wer
  - cer
"""

FULL_YAML = """
experiment_name: experimento-01
logging:
  mode: verbose
  output_file: logs/exp.log
retry:
  max_attempts: 5
  backoff_factor: 3.0
transcription:
  provider: whisper
  model: whisper-1
refinement:
  - provider: openai
    model: gpt-4o
    prompt_file: prompts/minimalist.yaml
  - provider: anthropic
    model: claude-opus-4-7
    prompt_file: prompts/rich_context.yaml
metrics:
  - wer
  - cer
  - bertscore
catalog_path: data/catalogo.csv
drive:
  credentials_path: credentials.json
  token_path: token.json
  audio_dir: data/inputs
results_path: results
"""


def test_minimal_config():
    config = ExperimentConfig(**{"experiment_name": "teste", "metrics": ["wer"]})
    assert config.experiment_name == "teste"
    assert config.logging.mode == "normal"
    assert config.retry.max_attempts == 3
    assert config.transcription.model == "whisper-1"
    assert config.refinement == []


def test_full_config():
    data = yaml.safe_load(FULL_YAML)
    config = ExperimentConfig(**data)
    assert config.experiment_name == "experimento-01"
    assert config.logging.mode == "verbose"
    assert config.retry.max_attempts == 5
    assert config.retry.backoff_factor == 3.0
    assert len(config.refinement) == 2
    assert config.refinement[0].provider == "openai"
    assert config.refinement[1].model == "claude-opus-4-7"
    assert config.metrics == ["wer", "cer", "bertscore"]
    assert config.catalog_path == "data/catalogo.csv"
    assert config.drive.audio_dir == "data/inputs"


def test_load_config_from_file(tmp_path):
    config_file = tmp_path / "test.yaml"
    config_file.write_text(MINIMAL_YAML, encoding="utf-8")
    config = load_config(config_file)
    assert config.experiment_name == "teste"
    assert config.metrics == ["wer", "cer"]


def test_missing_experiment_name_raises():
    with pytest.raises(Exception):
        ExperimentConfig(**{"metrics": ["wer"]})


def test_refinement_config_fields():
    ref = RefinementConfig(
        provider="google",
        model="gemini-1.5-pro",
        prompt_file="prompts/minimalist.yaml",
    )
    assert ref.provider == "google"
    assert ref.model == "gemini-1.5-pro"


def test_runs_and_split_defaults():
    config = ExperimentConfig(**{"experiment_name": "teste"})
    assert config.transcription.runs == 1
    assert config.transcription.cache is True
    assert config.transcription.cache_dir is None
    assert config.split == "dev"


@pytest.mark.parametrize("runs", [0, -1])
def test_runs_must_be_positive(runs):
    with pytest.raises(Exception):
        ExperimentConfig(**{"experiment_name": "teste", "transcription": {"runs": runs}})


def test_invalid_split_raises():
    with pytest.raises(Exception):
        ExperimentConfig(**{"experiment_name": "teste", "split": "train"})
