import json
import os
from pathlib import Path


CONFIG_ENV = "OPENFINANCE_CONFIG"
TOKEN_CACHE_ENV = "OPENFINANCE_TOKEN_CACHE"
HOME_ENV = "OPENFINANCE_HOME"

DEFAULT_PARTICIPANTS_URL = "https://data.directory.openbankingbrasil.org.br/participants"
DEFAULT_SANDBOX_PARTICIPANTS_URL = (
    "https://data.sandbox.directory.openbankingbrasil.org.br/participants"
)

CONFIG_KEYS = (
    "base_url",
    "accounts_url",
    "consents_url",
    "resources_url",
    "participants_url",
    "token_url",
    "client_id",
    "client_secret",
    "certificate",
    "certificate_key",
    "mock",
)

SECRET_KEYS = ("client_secret", "access_token", "refresh_token")


class ConfigError(Exception):
    """Raised when local CLI configuration cannot be read or used."""


def openfinance_home():
    custom_home = os.environ.get(HOME_ENV)
    if custom_home:
        return Path(custom_home).expanduser()
    return Path.home() / ".openfinance"


def config_path():
    custom_path = os.environ.get(CONFIG_ENV)
    if custom_path:
        return Path(custom_path).expanduser()
    return openfinance_home() / "config.json"


def token_cache_path():
    custom_path = os.environ.get(TOKEN_CACHE_ENV)
    if custom_path:
        return Path(custom_path).expanduser()
    return openfinance_home() / "token_cache.json"


def load_json_file(path):
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ConfigError("Invalid JSON in %s: %s" % (path, exc))
    if not isinstance(data, dict):
        raise ConfigError("Expected JSON object in %s" % path)
    return data


def save_json_file(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_config():
    data = load_json_file(config_path())
    return normalize_config(data)


def save_config(data):
    normalized = normalize_config(data)
    save_json_file(config_path(), normalized)
    return normalized


def normalize_config(data):
    result = {}
    for key in CONFIG_KEYS:
        value = data.get(key)
        if value is None or value == "":
            continue
        if key == "mock":
            result[key] = parse_bool(value)
        else:
            result[key] = str(value)
    return result


def parse_bool(value):
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "on"):
        return True
    if text in ("0", "false", "no", "n", "off"):
        return False
    raise ConfigError("Invalid boolean value: %s" % value)


def update_config(**updates):
    current = load_config()
    for key, value in updates.items():
        if key not in CONFIG_KEYS:
            raise ConfigError("Unsupported config key: %s" % key)
        if value is None:
            continue
        if value == "":
            current.pop(key, None)
        elif key == "mock":
            current[key] = parse_bool(value)
        else:
            current[key] = str(value)
    return save_config(current)


def masked_config(data):
    result = {}
    for key, value in data.items():
        if key in SECRET_KEYS and value:
            result[key] = "***"
        else:
            result[key] = value
    return result


def load_token_cache():
    return load_json_file(token_cache_path())


def save_token_cache(data):
    save_json_file(token_cache_path(), data)
    return data
