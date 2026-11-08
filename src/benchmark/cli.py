import asyncio
from pathlib import Path

import click
from dotenv import load_dotenv

from .config import load_config
from .config.schema import AnalysisConfig
from .pipeline import Pipeline
from .reporting.html_reporter import write_html
from .reporting.json_reporter import read_json
from .reporting.stats import analyze as run_analysis
from .reporting.stats import write_stats_json
from .utils.logging import setup_logging


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option(
    "--config", "-c",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Caminho para o arquivo YAML do experimento.",
)
def run(config: Path) -> None:
    """Executa o pipeline de benchmark."""
    load_dotenv()
    cfg = load_config(config)
    setup_logging(cfg.logging.mode, cfg.logging.output_file)

    drive_service = None
    credentials_path = Path(cfg.drive.credentials_path)
    token_path = Path(cfg.drive.token_path)
    if credentials_path.exists():
        from .gdrive import get_drive_service
        drive_service = get_drive_service(credentials_path, token_path)
    else:
        click.echo(
            f"Aviso: {credentials_path} não encontrado. "
            "Downloads do Google Drive desativados — use arquivos já em cache.",
            err=True,
        )

    pipeline = Pipeline(cfg, drive_service=drive_service)
    run_dir = asyncio.run(pipeline.run())
    click.echo(f"\nResultados salvos em: {run_dir}")


@cli.command()
@click.argument("results_json", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--output", "-o",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Pasta de saída (padrão: a pasta do results.json).",
)
@click.option(
    "--severe-threshold",
    type=click.FloatRange(min=0.0, min_open=True),
    default=AnalysisConfig().severe_failure_threshold,
    show_default=True,
    help="Piora na métrica acima da qual uma avaliação conta como falha grave.",
)
@click.option("--seed", type=int, default=AnalysisConfig().seed, show_default=True)
def analyze(results_json: Path, output: Path | None, severe_threshold: float, seed: int) -> None:
    """Refaz a análise estatística e o relatório HTML a partir de um results.json."""
    results = read_json(results_json)
    if not results:
        raise click.ClickException(f"Nenhum resultado em {results_json}")

    config = AnalysisConfig(severe_failure_threshold=severe_threshold, seed=seed)
    metric_names = [k for k in results[0].metrics if any(r.metrics.get(k) is not None for r in results)]
    analysis = run_analysis(results, metric_names, config)

    out_dir = output or results_json.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    write_stats_json(analysis, out_dir / "stats.json")
    write_html(results, out_dir / "report.html", results_json.parent.name, analysis=analysis)
    click.echo(f"Análise salva em: {out_dir}")


def main() -> None:
    cli()
