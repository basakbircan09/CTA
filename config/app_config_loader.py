import yaml
from pathlib import Path


def load_app_config(config_path: Path = None) -> dict:
    if config_path is None:
        config_path = Path(__file__).parent / "app_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)
