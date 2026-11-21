import os
from pathlib import Path

try:  # optional: read os-lab/.env if python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
except ImportError:
    pass


class ConfigError(RuntimeError):
    pass


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ConfigError("DATABASE_URL is not set. Copy .env.example to .env (project root) and edit it.")
    return url
