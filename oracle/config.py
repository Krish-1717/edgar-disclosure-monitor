"""Settings loaded from the environment / ``.env`` (never hardcode secrets)."""
from __future__ import annotations

import os
import pathlib
import re
from dataclasses import dataclass, field

from . import TIER1_FORMS

SEC_MAX_RPS = 10.0          # SEC fair-access ceiling (requests / second, all hosts)
DEFAULT_RPS = 8.0           # stay comfortably below the ceiling
DEFAULT_CORS = ("https://krish-1717.github.io",)

_EMAIL_RE = re.compile(r"[^\s@<>()]+@[^\s@<>()]+\.[A-Za-z]{2,}")


class ConfigError(ValueError):
    """Raised for invalid or missing configuration."""


def validate_user_agent(user_agent: str | None) -> str:
    """SEC requires a descriptive User-Agent with a contact email.

    Accepts e.g. ``"Jane Doe jane@example.com"`` or
    ``"ORACLE/0.1 (Jane Doe; jane@example.com)"``.
    """
    ua = (user_agent or "").strip().strip('"').strip("'")
    if not ua or not _EMAIL_RE.search(ua) or len(ua.split()) < 2:
        raise ConfigError(
            "Set ORACLE_USER_AGENT (or EDGAR_USER_AGENT) in .env to a descriptive "
            "User-Agent with a contact email, e.g. 'Jane Doe jane@example.com'. "
            "SEC returns 403 for requests without one."
        )
    return ua


def _load_dotenv(env_file: str | os.PathLike | None) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # python-dotenv is optional at runtime
        return
    load_dotenv(env_file, override=False)


def parse_forms(value: str | None) -> tuple[str, ...]:
    if not value:
        return TIER1_FORMS
    forms = [f.strip().upper() for f in value.split(",") if f.strip()]
    # "10-K/A" means the same as "10-K": amendments are always tracked.
    out: list[str] = []
    for f in forms:
        base = f[:-2] if f.endswith("/A") else f
        if base not in out:
            out.append(base)
    return tuple(out)


@dataclass
class Settings:
    user_agent: str | None
    db_path: pathlib.Path = pathlib.Path("data/oracle/oracle.db")
    data_dir: pathlib.Path = pathlib.Path("data/oracle/documents")
    max_rps: float = DEFAULT_RPS
    forms: tuple[str, ...] = TIER1_FORMS
    cors_origins: tuple[str, ...] = field(default_factory=lambda: DEFAULT_CORS)

    def __post_init__(self) -> None:
        if not (0 < self.max_rps <= SEC_MAX_RPS):
            raise ConfigError(f"max_rps must be in (0, {SEC_MAX_RPS}] (SEC fair access)")

    @classmethod
    def from_env(cls, env_file: str | os.PathLike | None = None) -> "Settings":
        _load_dotenv(env_file)
        env = os.environ
        cors = tuple(
            o.strip() for o in env.get("ORACLE_CORS_ORIGINS", ",".join(DEFAULT_CORS)).split(",")
            if o.strip()
        )
        return cls(
            user_agent=env.get("ORACLE_USER_AGENT") or env.get("EDGAR_USER_AGENT"),
            db_path=pathlib.Path(env.get("ORACLE_DB_PATH", "data/oracle/oracle.db")),
            data_dir=pathlib.Path(env.get("ORACLE_DATA_DIR", "data/oracle/documents")),
            max_rps=float(env.get("ORACLE_MAX_RPS", DEFAULT_RPS)),
            forms=parse_forms(env.get("ORACLE_FORMS")),
            cors_origins=cors,
        )
