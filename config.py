import json
from pathlib import Path

REQUIRED_KEYS = ["recipient_email", "default_location", "nyt_api_key", "anthropic_api_key", "weatherkit"]
REQUIRED_WEATHERKIT_KEYS = ["team_id", "service_id", "key_id", "key_file"]

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
    wk = cfg.get("weatherkit") or {}
    for sub in REQUIRED_WEATHERKIT_KEYS:
        if sub not in wk:
            raise ConfigError(f"Missing required weatherkit config key: {sub}")
        if not wk[sub] or wk[sub] == "FILL_IN":
            raise ConfigError(f"weatherkit config key not filled in: {sub}")
    return cfg
