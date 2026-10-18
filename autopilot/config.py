import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DATA = ROOT / "data"
QUEUE = ROOT / "queue"


def load_config():
    with open(ROOT / "config.yaml") as f:
        cfg = yaml.safe_load(f)
    cfg["calendar"] = {int(k): v for k, v in cfg["calendar"].items()}
    return cfg


def load_env():
    """Read .env for local runs. GitHub Actions passes secrets as real env vars."""
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
