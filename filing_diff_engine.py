"""
filing_diff_engine.py — Section-by-section diff engine for SEC filings.

Compares consecutive 10-K/10-Q filings to detect added, removed, and changed
paragraphs. Scores materiality using keyword overlap and change magnitude.

Usage:
    engine = FilingDiffEngine()
    result = engine.diff(filing_text_a, filing_text_b)
    print(f"Materiality score: {result.materiality_score:.2f}")
    for change in result.changes[:5]:
        print(change)
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Section headers for 10-K / 10-Q
# ---------------------------------------------------------------------------

SECTION_PATTERNS: dict[str, str] = {
    "item_1":   r"item\s+1[^a-z].*business",
    "item_1a":  r"item\s+1a.*risk\s+factor",
    "item_1b":  r"item\s+1b.*unresolved",
    "item_2":   r"item\s+2[^a-z].*properties",
    "item_3":   r"item\s+3[^a-z].*legal\s+proc",
    "item_4":   r"item\s+4[^a-z].*mine\s+safety",
    "item_5":   r"item\s+5[^a-z].*market",
    "item_6":   r"item\s+6[^a-z].*selected",
    "item_7":   r"item\s+7[^a-z].*management.*discussion",
    "item_7a":  r"item\s+7a.*quantitative",
    "item_8":   r"item\s+8[^a-z].*financial\s+statement",
    "item_9":   r"item\s+9[^a-z].*changes.*disagreement",
    "item_9a":  r"item\s+9a.*controls",
    "item_9b":  r"item\s+9b.*other",
    "item_10":  r"item\s+10[^a-z].*directors",
    "item_11":  r"item\s+11[^a-z].*executive\s+comp",
    "item_12":  r"item\s+12[^a-z].*security\s+ownership",
    "item_13":  r"item\s+13[^a-z].*certain\s+relationships",
    "item_14":  r"item\s+14[^a-z].*principal\s+account",
    "item_15":  r"item\s+15[^a-z].*exhibits",
}

# High-materiality keywords that inflate the diff score
MATERIAL_KEYWORDS: list[str] = [
    "going concern", "material weakness", "restatement", "fraud",
    "investigation", "subpoena", "bankruptcy", "default", "litigation",
    "contingent liability", "impairment", "goodwill write", "regulatory action",
    "fda rejection", "sec inquiry", "whistleblower", "class action",
    "derivative suit", "data breach", "cybersecurity incident",
    "dividend suspension", "guidance withdrawal", "ceo departure",
    "related party", "insider", "sanction",
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FilingSection:
    name: str          # e.g. "item_1a"
    label: str         # human label e.g. "Risk Factors"
    text: str
    word_count: int = 0
    fingerprint: str = ""

    def __post_init__(self):
        self.word_count = len(self.text.split())
        self.fingerprint = hashlib.sha256(
            self.text.encode("utf-8", errors="ignore")
        ).hexdigest()[:16]


@dataclass
class ParagraphChange:
    change_type: str   # "added" | "removed" | "changed"
    section: str
    text_before: str
    text_after: str
    ratio: float       # similarity ratio 0-1 (1=identical)
    material_keywords: list = field(default_factory=list)

    @property
    def is_material(self) -> bool:
        return bool(self.material_keywords) or self.ratio < 0.6


@dataclass
class SectionDiff:
    section: str
    status: str        # "unchanged" | "modified" | "added" | "removed"
    words_before: int
    words_after: int
    similarity: float  # 0-1
    changes: list = field(default_factory=list)

    @property
    def word_delta(self) -> int:
        return self.words_after - self.words_before


@dataclass
class DiffResult:
    ticker: str
    filing_date_a: str
    filing_date_b: str
    section_diffs: list
    all_changes: list
    materiality_score: float    # 0-1
    material_keywords_found: list
    word_count_before: int
    word_count_after: int
    generated_at: str

    def summary(self) -> str:
        added = sum(1 for s in self.section_diffs if s.status == "added")
        removed = sum(1 for s in self.section_diffs if s.status == "removed")
        modified = sum(1 for s in self.section_diffs if s.status == "modified")
        return (
            f"Filing diff {self.ticker}: {self.filing_date_a} → {self.filing_date_b}\n"
            f"Sections: {modified} modified, {added} added, {removed} removed\n"
            f"Words: {self.word_count_before} → {self.word_count_after} "
            f"({self.word_count_after - self.word_count_before:+d})\n"
            f"Materiality score: {self.materiality_score:.2f}\n"
            f"Keywords: {', '.join(self.material_keywords_found[:5]) or 'none'}"
        )


# ---------------------------------------------------------------------------
# Diff Engine
# ---------------------------------------------------------------------------

class FilingDiffEngine:
    """
    Compares two filing texts section by section.

    Usage:
        engine = FilingDiffEngine()
        result = engine.diff(text_a, text_b, ticker="NVDA",
                             date_a="2025-02-01", date_b="2026-02-01")
    """

    def __init__(self, min_para_words: int = 20):
        self.min_para_words = min_para_words

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _split_sections(self, text: str) -> dict:
        """Split filing text into named sections."""
        text_lower = text.lower()
        section_positions: list = []

        for name, pattern in SECTION_PATTERNS.items():
            for m in re.finditer(pattern, text_lower):
                section_positions.append((m.start(), name))

        section_positions.sort(key=lambda x: x[0])
        sections: dict = {}
        for i, (pos, name) in enumerate(section_positions):
            end = section_positions[i + 1][0] if i + 1 < len(section_positions) else len(text)
            chunk = text[pos:end].strip()
            if len(chunk) > 100:
                label = name.replace("_", " ").upper()
                sections[name] = FilingSection(name=name, label=label, text=chunk)

        if not sections:
            # Fallback: treat entire filing as one section
            sections["full"] = FilingSection(name="full", label="FULL FILING", text=text)

        return sections

    def _split_paragraphs(self, text: str) -> list:
        """Split text into meaningful paragraphs."""
        paras = re.split(r"\n{2,}", text)
        return [p.strip() for p in paras
                if len(p.split()) >= self.min_para_words]

    def _find_material_keywords(self, text: str) -> list:
        text_lower = text.lower()
        return [kw for kw in MATERIAL_KEYWORDS if kw in text_lower]

    # ------------------------------------------------------------------
    # Section diff
    # ------------------------------------------------------------------

    def _diff_section(self, name: str,
                      sec_a: Optional[FilingSection],
                      sec_b: Optional[FilingSection]) -> SectionDiff:
        if sec_a is None:
            return SectionDiff(section=name, status="added",
                               words_before=0, words_after=sec_b.word_count,
                               similarity=0.0)
        if sec_b is None:
            return SectionDiff(section=name, status="removed",
                               words_before=sec_a.word_count, words_after=0,
                               similarity=0.0)
        if sec_a.fingerprint == sec_b.fingerprint:
            return SectionDiff(section=name, status="unchanged",
                               words_before=sec_a.word_count,
                               words_after=sec_b.word_count, similarity=1.0)

        ratio = difflib.SequenceMatcher(None, sec_a.text, sec_b.text).ratio()
        changes = self._diff_paragraphs(name, sec_a.text, sec_b.text)
        return SectionDiff(
            section=name, status="modified",
            words_before=sec_a.word_count, words_after=sec_b.word_count,
            similarity=round(ratio, 4), changes=changes,
        )

    def _diff_paragraphs(self, section: str, text_a: str, text_b: str) -> list:
        paras_a = self._split_paragraphs(text_a)
        paras_b = self._split_paragraphs(text_b)
        matcher = difflib.SequenceMatcher(None, paras_a, paras_b)
        changes = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            if tag == "replace":
                for ia, ja in zip(range(i1, i2), range(j1, j2)):
                    before = paras_a[ia] if ia < len(paras_a) else ""
                    after  = paras_b[ja] if ja < len(paras_b) else ""
                    ratio  = difflib.SequenceMatcher(None, before, after).ratio()
                    kws    = self._find_material_keywords(before + " " + after)
                    changes.append(ParagraphChange(
                        change_type="changed", section=section,
                        text_before=before[:500], text_after=after[:500],
                        ratio=round(ratio, 4), material_keywords=kws,
                    ))
            elif tag == "insert":
                for ja in range(j1, j2):
                    text = paras_b[ja]
                    kws  = self._find_material_keywords(text)
                    changes.append(ParagraphChange(
                        change_type="added", section=section,
                        text_before="", text_after=text[:500],
                        ratio=0.0, material_keywords=kws,
                    ))
            elif tag == "delete":
                for ia in range(i1, i2):
                    text = paras_a[ia]
                    kws  = self._find_material_keywords(text)
                    changes.append(ParagraphChange(
                        change_type="removed", section=section,
                        text_before=text[:500], text_after="",
                        ratio=0.0, material_keywords=kws,
                    ))

        return changes

    # ------------------------------------------------------------------
    # Materiality score
    # ------------------------------------------------------------------

    def score_materiality(self, diff: DiffResult) -> float:
        """
        0-1 composite materiality score.
        Weights: keyword hits (40%) + structural change (30%) + volume change (30%).
        """
        # Keyword component
        kw_score = min(len(diff.material_keywords_found) / 5.0, 1.0) * 0.40

        # Structural: fraction of sections modified/added/removed
        total_secs = len(diff.section_diffs) or 1
        changed_secs = sum(1 for s in diff.section_diffs if s.status != "unchanged")
        struct_score = (changed_secs / total_secs) * 0.30

        # Volume: normalized word delta
        total_words = diff.word_count_before or 1
        delta_ratio = min(abs(diff.word_count_after - diff.word_count_before) / total_words, 1.0)
        vol_score = delta_ratio * 0.30

        return round(kw_score + struct_score + vol_score, 4)

    # ------------------------------------------------------------------
    # Main diff
    # ------------------------------------------------------------------

    def diff(self, text_a: str, text_b: str,
             ticker: str = "", date_a: str = "", date_b: str = "") -> DiffResult:
        """
        Compare two filing texts. Returns a DiffResult with per-section diffs,
        all paragraph changes, and a materiality score.
        """
        secs_a = self._split_sections(text_a)
        secs_b = self._split_sections(text_b)
        all_keys = set(secs_a) | set(secs_b)

        section_diffs = []
        all_changes = []
        for key in sorted(all_keys):
            sd = self._diff_section(key, secs_a.get(key), secs_b.get(key))
            section_diffs.append(sd)
            all_changes.extend(sd.changes)

        all_kws = list({kw for ch in all_changes for kw in ch.material_keywords})
        total_a = sum(s.word_count for s in secs_a.values())
        total_b = sum(s.word_count for s in secs_b.values())

        result = DiffResult(
            ticker=ticker,
            filing_date_a=date_a,
            filing_date_b=date_b,
            section_diffs=section_diffs,
            all_changes=all_changes,
            materiality_score=0.0,
            material_keywords_found=all_kws,
            word_count_before=total_a,
            word_count_after=total_b,
            generated_at=datetime.utcnow().isoformat(),
        )
        result.materiality_score = self.score_materiality(result)
        return result

    def diff_files(self, path_a: Path, path_b: Path,
                   ticker: str = "", date_a: str = "", date_b: str = "") -> DiffResult:
        return self.diff(
            path_a.read_text(errors="ignore"),
            path_b.read_text(errors="ignore"),
            ticker=ticker, date_a=date_a, date_b=date_b,
        )

    def export_json(self, result: DiffResult, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump({
                "ticker": result.ticker,
                "filing_date_a": result.filing_date_a,
                "filing_date_b": result.filing_date_b,
                "materiality_score": result.materiality_score,
                "material_keywords_found": result.material_keywords_found,
                "word_count_before": result.word_count_before,
                "word_count_after": result.word_count_after,
                "generated_at": result.generated_at,
                "section_diffs": [asdict(s) for s in result.section_diffs],
            }, f, indent=2)


if __name__ == "__main__":
    engine = FilingDiffEngine()
    text_a = """Item 1. Business
    We manufacture semiconductors for data center applications.
    
    Item 1A. Risk Factors
    Supply chain disruptions could impact our operations.
    Competition in the AI chip market is intense.
    
    Item 7. Management Discussion
    Revenue grew 20% year over year to $10 billion.
    """
    text_b = """Item 1. Business
    We manufacture semiconductors for data center and automotive applications.
    
    Item 1A. Risk Factors
    Supply chain disruptions could impact our operations.
    Competition in the AI chip market is intense.
    The company has received a subpoena from the SEC regarding revenue recognition.
    There is substantial doubt about our ability to continue as a going concern.
    
    Item 7. Management Discussion
    Revenue declined 5% year over year to $9.5 billion due to inventory correction.
    """
    result = engine.diff(text_a, text_b, ticker="DEMO", date_a="2025-01", date_b="2026-01")
    print(result.summary())
    for ch in result.all_changes:
        if ch.is_material:
            print(f"  [{ch.change_type.upper()}] {ch.section}: {ch.material_keywords}")
