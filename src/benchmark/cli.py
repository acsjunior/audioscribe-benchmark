import asyncio
from pathlib import Path

import click
from dotenv import load_dotenv

from .config import load_config
from .pipeline import Pipeline
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


def main() -> None:
    cli()
