#!/usr/bin/env python3
"""Create or update ForgeGov's local .env without printing secrets."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path
import secrets


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
EXAMPLE_PATH = ROOT / ".env.example"


def read_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def main() -> None:
    values = read_values(EXAMPLE_PATH)
    values.update(read_values(ENV_PATH))

    current_key = values.get("SAM_GOV_API_KEY", "")
    prompt = "SAM.gov API key"
    if current_key:
        prompt += " (press Enter to keep the current value)"
    entered_key = getpass(f"{prompt}: ").strip()
    if entered_key:
        values["SAM_GOV_API_KEY"] = entered_key

    if not values.get("DJANGO_SECRET_KEY") or values["DJANGO_SECRET_KEY"].startswith("replace-"):
        values["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(48)

    ordered_keys = [
        "DJANGO_SECRET_KEY",
        "DJANGO_DEBUG",
        "DJANGO_ALLOWED_HOSTS",
        "DATABASE_URL",
        "REDIS_URL",
        "CORS_ALLOWED_ORIGINS",
        "NEXT_PUBLIC_API_BASE_URL",
        "SAM_GOV_API_KEY",
        "SAM_GOV_BASE_URL",
        "SAM_LIVE_SEARCH_RATE",
        "SAM_DAILY_SYNC_LIMIT",
        "SAM_SYNC_ENABLED",
        "USASPENDING_BASE_URL",
    ]
    lines = [f"{key}={values.get(key, '')}" for key in ordered_keys]
    ENV_PATH.write_text("\n".join(lines) + "\n")
    print(f"Configured {ENV_PATH}. The file is ignored by Git.")


if __name__ == "__main__":
    main()
