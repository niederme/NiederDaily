import json
from pathlib import Path

REQUIRED_KEYS = ["recipient_email", "default_location", "nyt_api_key", "anthropic_api_key"]

class ConfigError(Exception):
    pass

def load_config(path: str = None) -> dict:
    if path is None:
        path = Path.home() / ".niederdaily" / "config.json"
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Config file not found: {p}")
    try:
        cfg = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config: {e}")
    for key in REQUIRED_KEYS:
        if key not in cfg:
            raise ConfigError(f"Missing required config key: {key}")
        if cfg[key] == "FILL_IN":
            raise ConfigError(f"Config key not filled in: {key}")
    return cfg
