from pathlib import Path

import yaml

from .schema import ExperimentConfig


def load_config(config_path: Path) -> ExperimentConfig:
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ExperimentConfig(**data)
