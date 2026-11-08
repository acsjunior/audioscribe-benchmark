from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from benchmark.cli import cli

CONFIG_YAML = """\
experiment_name: teste
metrics:
  - wer
drive:
  credentials_path: nao_existe_credentials.json
results_path: results
"""


@patch("benchmark.cli.Pipeline")
@patch("benchmark.cli.load_dotenv")
def test_run_command_success(mock_dotenv, mock_pipeline_cls, tmp_path):
    config_file = tmp_path / "test.yaml"
    config_file.write_text(CONFIG_YAML, encoding="utf-8")

    mock_pipeline = MagicMock()
    mock_pipeline.run = AsyncMock(return_value=tmp_path / "results" / "teste_20260503_120000")
    mock_pipeline_cls.return_value = mock_pipeline

    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--config", str(config_file)])

    assert result.exit_code == 0
    assert "Resultados salvos em:" in result.output
    mock_dotenv.assert_called_once()
    mock_pipeline_cls.assert_called_once()


def test_run_command_missing_config():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--config", "nao_existe.yaml"])
    assert result.exit_code != 0


def test_run_command_missing_config_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["run"])
    assert result.exit_code != 0
