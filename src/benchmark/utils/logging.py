import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

console = Console()


def setup_logging(mode: str, output_file: str) -> logging.Logger:
    log_path = Path(output_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if mode == "verbose" else logging.INFO

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )

    logging.basicConfig(
        level=level,
        handlers=[
            RichHandler(console=console, show_path=False, markup=True),
            file_handler,
        ],
    )

    return logging.getLogger("benchmark")
