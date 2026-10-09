"""filing_cache.py — Intelligent filing cache for EDGAR Disclosure Monitor."""
from __future__ import annotations
import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Domain types (lightweight stubs — real versions defined in other modules)
# ---------------------------------------------------------------------------

@dataclass
class ParsedFiling:
    ticker: str
    accession: str
    form_type: str
    sections: dict[str, str]
    filed_at: str = ""
    word_count: int = 0


@dataclass
class FilingDiff:
    ticker: str
    accession_new: str
    accession_old: str
    materiality_score: float
    changed_sections: list[str] = field(default_factory=list)
    diff_summary: str = ""


# ---------------------------------------------------------------------------
# TTLs
# ---------------------------------------------------------------------------

_TTL = {
    "filing": 30 * 24 * 3600,   # 30 days
    "diff":    7 * 24 * 3600,   # 7 days
    "news":    1 * 24 * 3600,   # 24 hours
}

_MAX_CACHE_BYTES = 500 * 1024 * 1024  # 500 MB


class FilingCache:
    """
    Disk-backed cache with TTL and LRU eviction.

    Layout:
        {cache_dir}/{ticker}/filing_{accession}.json
        {cache_dir}/{ticker}/diff_{acc_new}_{acc_old}.json
        {cache_dir}/{ticker}/news_{date}.json
    """

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Filing
    # ------------------------------------------------------------------

    def get_filing(self, ticker: str, accession: str) -> Optional[ParsedFiling]:
        path = self._filing_path(ticker, accession)
        obj = self._load(path, _TTL["filing"])
        if obj is None:
            return None
        return ParsedFiling(**obj)

    def set_filing(self, ticker: str, accession: str, filing: ParsedFiling) -> None:
        self._save(self._filing_path(ticker, accession), asdict(filing))

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def get_diff(self, ticker: str, accession_new: str, accession_old: str) -> Optional[FilingDiff]:
        path = self._diff_path(ticker, accession_new, accession_old)
        obj = self._load(path, _TTL["diff"])
        if obj is None:
            return None
        return FilingDiff(**obj)

    def set_diff(self, ticker: str, accession_new: str, accession_old: str, diff: FilingDiff) -> None:
        self._save(self._diff_path(ticker, accession_new, accession_old), asdict(diff))

    # ------------------------------------------------------------------
    # News score
    # ------------------------------------------------------------------

    def get_news_score(self, ticker: str, date_str: str) -> Optional[tuple[float, float, int]]:
        path = self._news_path(ticker, date_str)
        obj = self._load(path, _TTL["news"])
        if obj is None:
            return None
        return (obj["quality"], obj["composite"], obj["count"])

    def set_news_score(self, ticker: str, date_str: str, score: tuple[float, float, int]) -> None:
        quality, composite, count = score
        self._save(self._news_path(ticker, date_str), {
            "quality": quality, "composite": composite, "count": count
        })

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def evict_old(self, max_age_days: int = 30) -> int:
        """Remove files older than max_age_days. Returns count removed."""
        cutoff = time.time() - max_age_days * 86400
        removed = 0
        for root, _dirs, files in os.walk(self.cache_dir):
            for fname in files:
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    if os.path.getmtime(fpath) < cutoff:
                        os.remove(fpath)
                        removed += 1
                except OSError:
                    pass
        return removed

    def cache_stats(self) -> dict:
        total_files = 0
        total_bytes = 0
        oldest_mtime = float("inf")
        for root, _dirs, files in os.walk(self.cache_dir):
            for fname in files:
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    stat = os.stat(fpath)
                    total_files += 1
                    total_bytes += stat.st_size
                    if stat.st_mtime < oldest_mtime:
                        oldest_mtime = stat.st_mtime
                except OSError:
                    pass
        oldest_entry = (
            datetime.fromtimestamp(oldest_mtime).isoformat()
            if oldest_mtime < float("inf") else "N/A"
        )
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
        return {
            "total_files": total_files,
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
            "oldest_entry": oldest_entry,
            "hit_rate": round(hit_rate, 3),
            "hits": self._hits,
            "misses": self._misses,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _filing_path(self, ticker: str, accession: str) -> str:
        safe_acc = accession.replace("/", "_").replace(":", "_")
        return os.path.join(self.cache_dir, ticker.upper(), f"filing_{safe_acc}.json")

    def _diff_path(self, ticker: str, acc_new: str, acc_old: str) -> str:
        safe_new = acc_new.replace("/", "_")
        safe_old = acc_old.replace("/", "_")
        return os.path.join(self.cache_dir, ticker.upper(), f"diff_{safe_new}_{safe_old}.json")

    def _news_path(self, ticker: str, date_str: str) -> str:
        return os.path.join(self.cache_dir, ticker.upper(), f"news_{date_str}.json")

    def _load(self, path: str, ttl: int) -> Optional[dict]:
        if not os.path.exists(path):
            self._misses += 1
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                wrapper = json.load(fh)
            cached_at = wrapper.get("_cached_at", 0)
            if time.time() - cached_at > ttl:
                self._misses += 1
                return None
            payload_json = json.dumps(wrapper["data"], sort_keys=True)
            expected = wrapper.get("_sha256", "")
            actual = hashlib.sha256(payload_json.encode()).hexdigest()
            if expected and expected != actual:
                self._misses += 1
                return None
            self._hits += 1
            return wrapper["data"]
        except (OSError, json.JSONDecodeError, KeyError):
            self._misses += 1
            return None

    def _save(self, path: str, data: dict) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload_json = json.dumps(data, sort_keys=True)
        sha = hashlib.sha256(payload_json.encode()).hexdigest()
        wrapper = {"_cached_at": time.time(), "_sha256": sha, "data": data}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(wrapper, fh)
        stats = self.cache_stats()
        if stats["total_size_mb"] * 1024 * 1024 > _MAX_CACHE_BYTES:
            self.evict_old(max_age_days=7)


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = FilingCache(cache_dir=tmpdir)

        filing = ParsedFiling(
            ticker="NVDA", accession="0001234567-24-000001",
            form_type="10-K", sections={"risk_factors": "...", "md_a": "..."},
            filed_at="2024-03-01", word_count=45000,
        )
        cache.set_filing("NVDA", filing.accession, filing)
        loaded = cache.get_filing("NVDA", filing.accession)
        assert loaded is not None and loaded.ticker == "NVDA"
        print("Filing cache: OK")

        diff = FilingDiff(
            ticker="NVDA", accession_new="0001234567-24-000001",
            accession_old="0001234567-23-000001",
            materiality_score=0.82, changed_sections=["risk_factors"],
            diff_summary="Risk factors expanded significantly.",
        )
        cache.set_diff("NVDA", diff.accession_new, diff.accession_old, diff)
        loaded_diff = cache.get_diff("NVDA", diff.accession_new, diff.accession_old)
        assert loaded_diff is not None and abs(loaded_diff.materiality_score - 0.82) < 1e-6
        print("Diff cache: OK")

        cache.set_news_score("NVDA", "2024-03-01", (0.78, 0.65, 12))
        ns = cache.get_news_score("NVDA", "2024-03-01")
        assert ns is not None and abs(ns[0] - 0.78) < 1e-6
        print("News score cache: OK")

        print("Stats:", cache.cache_stats())
