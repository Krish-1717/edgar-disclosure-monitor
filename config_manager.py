"""config_manager.py — Centralized configuration management for EDGAR Disclosure Monitor."""
from __future__ import annotations
import json
import os
from copy import deepcopy
from typing import Any, Optional

DEFAULT_CONFIG: dict = {
    "edgar": {
        "rate_limit_per_sec": 10,
        "cache_dir": "data/cache",
        "max_filings_to_compare": 2,
        "supported_forms": ["10-K", "10-Q"],
    },
    "news": {
        "window_days": 3,
        "quality_threshold": 0.65,
        "count_weight": 0.35,
        "quality_weight": 0.65,
    },
    "scoring": {
        "critical_threshold": 80,
        "high_threshold": 60,
        "medium_threshold": 40,
        "low_threshold": 20,
    },
    "notifications": {
        "email": {
            "enabled": False,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "",
            "smtp_password": "",
            "from_addr": "",
            "to_addrs": [],
        },
        "webhook": {
            "enabled": False,
            "url": "",
            "secret": "",
        },
        "in_app": {
            "enabled": True,
            "path": "data/notifications.jsonl",
        },
    },
}

# Environment variable prefix
_ENV_PREFIX = "EDGAR_"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into a copy of base."""
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _apply_env_overrides(cfg: dict, prefix: str = _ENV_PREFIX) -> dict:
    """
    Apply environment variable overrides.
    EDGAR_EDGAR__RATE_LIMIT_PER_SEC=5  →  cfg["edgar"]["rate_limit_per_sec"] = 5
    (double underscore separates nesting levels)
    """
    cfg = deepcopy(cfg)
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        path = key[len(prefix):].lower().split("__")
        node = cfg
        for part in path[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node = None
                break
            node = node[part]
        if node is None:
            continue
        leaf = path[-1]
        if leaf in node:
            existing = node[leaf]
            try:
                if isinstance(existing, bool):
                    node[leaf] = value.lower() in ("1", "true", "yes")
                elif isinstance(existing, int):
                    node[leaf] = int(value)
                elif isinstance(existing, float):
                    node[leaf] = float(value)
                elif isinstance(existing, list):
                    node[leaf] = [v.strip() for v in value.split(",")]
                else:
                    node[leaf] = value
            except (ValueError, TypeError):
                node[leaf] = value
    return cfg


class ConfigManager:
    """Load, validate, and provide dot-notation access to EDGAR config."""

    def __init__(self, config_path: str = "config/edgar_config.json"):
        self._config_path = config_path
        file_cfg: dict = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as fh:
                file_cfg = json.load(fh)
        merged = _deep_merge(DEFAULT_CONFIG, file_cfg)
        self._cfg = _apply_env_overrides(merged)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Dot-notation access to config values.
        Examples:
            config.get('edgar.rate_limit_per_sec')  → 10
            config.get('notifications.email.enabled')  → False
        """
        parts = key.split(".")
        node: Any = self._cfg
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key: str, value: Any) -> None:
        """Set a config value by dot-notation key (in-memory only)."""
        parts = key.split(".")
        node = self._cfg
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value

    def validate(self) -> list[str]:
        """
        Validate config and return a list of error messages.
        Empty list means config is valid.
        """
        errors: list[str] = []

        rls = self.get("edgar.rate_limit_per_sec")
        if not isinstance(rls, (int, float)) or rls <= 0:
            errors.append("edgar.rate_limit_per_sec must be a positive number")
        if not isinstance(self.get("edgar.supported_forms"), list):
            errors.append("edgar.supported_forms must be a list")

        cw = self.get("news.count_weight", 0)
        qw = self.get("news.quality_weight", 0)
        if abs((cw + qw) - 1.0) > 1e-6:
            errors.append(f"news.count_weight + news.quality_weight must equal 1.0 (got {cw + qw})")

        ct = self.get("scoring.critical_threshold", 0)
        ht = self.get("scoring.high_threshold", 0)
        mt = self.get("scoring.medium_threshold", 0)
        lt = self.get("scoring.low_threshold", 0)
        if not (ct > ht > mt > lt >= 0):
            errors.append("scoring thresholds must satisfy critical > high > medium > low >= 0")

        if self.get("notifications.email.enabled"):
            if not self.get("notifications.email.smtp_host"):
                errors.append("notifications.email.smtp_host is required when email is enabled")
            if not self.get("notifications.email.from_addr"):
                errors.append("notifications.email.from_addr is required when email is enabled")
            if not self.get("notifications.email.to_addrs"):
                errors.append("notifications.email.to_addrs must be non-empty when email is enabled")

        if self.get("notifications.webhook.enabled"):
            if not self.get("notifications.webhook.url"):
                errors.append("notifications.webhook.url is required when webhook is enabled")

        return errors

    def save(self, path: Optional[str] = None) -> None:
        """Save current in-memory config to a JSON file."""
        target = path or self._config_path
        os.makedirs(os.path.dirname(target) if os.path.dirname(target) else ".", exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(self._cfg, fh, indent=2)
        print(f"Config saved to {target}")

    def as_dict(self) -> dict:
        return deepcopy(self._cfg)

    def __repr__(self) -> str:
        return f"ConfigManager(path={self._config_path!r})"


if __name__ == "__main__":
    cfg = ConfigManager()
    print("Loaded config (defaults):")
    print(json.dumps(cfg.as_dict(), indent=2))

    print("\nDot-notation access:")
    print(f"  edgar.rate_limit_per_sec = {cfg.get('edgar.rate_limit_per_sec')}")
    print(f"  news.count_weight        = {cfg.get('news.count_weight')}")
    print(f"  scoring.critical_threshold = {cfg.get('scoring.critical_threshold')}")
    print(f"  notifications.in_app.enabled = {cfg.get('notifications.in_app.enabled')}")

    errors = cfg.validate()
    if errors:
        print("\nValidation errors:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\nConfig is valid.")
