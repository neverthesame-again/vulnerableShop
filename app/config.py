"""Application settings, read from environment variables at call time."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str
    demo_api_key: str | None
    allowed_fetch_hosts: frozenset[str]
    fetch_timeout_seconds: float
    max_fetch_bytes: int


def _parse_hosts(raw: str) -> frozenset[str]:
    return frozenset(h.strip().lower() for h in raw.split(",") if h.strip())


def get_settings() -> Settings:
    return Settings(
        db_path=os.getenv("VULNSHOP_DB_PATH", "vulnerable_shop.db"),
        demo_api_key=os.getenv("VULNSHOP_DEMO_API_KEY"),
        # Comma-separated "host" or "host:port" entries that /fetch-url may contact.
        allowed_fetch_hosts=_parse_hosts(os.getenv("VULNSHOP_ALLOWED_FETCH_HOSTS", "example.test")),
        fetch_timeout_seconds=float(os.getenv("VULNSHOP_FETCH_TIMEOUT", "5")),
        max_fetch_bytes=int(os.getenv("VULNSHOP_MAX_FETCH_BYTES", "65536")),
    )
