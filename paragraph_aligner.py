"""
paragraph_aligner.py — Paragraph Alignment and Diff Engine

Aligns paragraphs between two versions of the same section using
TF-IDF cosine similarity (greedy best match), then runs word-level
difflib to produce insertion/deletion spans for revised pairs.

Thresholds (from the build plan):
  ≥ 0.95  → unchanged
  0.50–0.95 → revised
  < 0.50  → added or removed
"""
from __future__ import annotations
import difflib
import math
import re
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class AlignedPair:
    change_type: str        # 'unchanged' | 'revised' | 'added' | 'removed'
    new_text: str = ""
    old_text: str = ""
    similarity: float = 0.0
    added_words: list[str] = field(default_factory=list)
    removed_words: list[str] = field(default_factory=list)

    @property
    def word_delta(self) -> int:
        return len(self.new_text.split()) - len(self.old_text.split())

    def to_dict(self) -> dict:
        return {
            "change_type":   self.change_type,
            "new_text":      self.new_text,
            "old_text":      self.old_text,
            "similarity":    round(self.similarity, 4),
            "added_words":   len(self.added_words),
            "removed_words": len(self.removed_words),
            "word_delta":    self.word_delta,
        }


# ── TF-IDF helpers ─────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def _tf(tokens: list[str]) -> Counter:
    c = Counter(tokens)
    total = max(len(tokens), 1)
    return Counter({t: n / total for t, n in c.items()})


def _idf(docs: list[list[str]]) -> dict[str, float]:
    N = len(docs)
    df: Counter = Counter()
    for doc in docs:
        df.update(set(doc))
    return {t: math.log((N + 1) / (n + 1)) + 1.0 for t, n in df.items()}


def _tfidf_vec(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = _tf(tokens)
    return {t: tf[t] * idf.get(t, 1.0) for t in tf}


def _cosine(v1: dict, v2: dict) -> float:
    keys = set(v1) & set(v2)
    num = sum(v1[k] * v2[k] for k in keys)
    d1  = math.sqrt(sum(x * x for x in v1.values()))
    d2  = math.sqrt(sum(x * x for x in v2.values()))
    return num / (d1 * d2) if d1 > 0 and d2 > 0 else 0.0


# ── Main aligner ──────────────────────────────────────────────────────────────

def align_paragraphs(
    new_paragraphs: list[str],
    old_paragraphs: list[str],
    unchanged_threshold: float = 0.95,
    match_threshold:     float = 0.50,
) -> list[AlignedPair]:
    """
    Align new_paragraphs against old_paragraphs using TF-IDF cosine, greedy best match.
    Returns list of AlignedPair with change_type labels.
    """
    if not new_paragraphs and not old_paragraphs:
        return []

    all_docs = [_tokenize(p) for p in new_paragraphs + old_paragraphs]
    idf = _idf(all_docs)

    new_vecs = [_tfidf_vec(_tokenize(p), idf) for p in new_paragraphs]
    old_vecs = [_tfidf_vec(_tokenize(p), idf) for p in old_paragraphs]

    # Build full similarity matrix
    sim: list[list[float]] = []
    for nv in new_vecs:
        row = [_cosine(nv, ov) for ov in old_vecs]
        sim.append(row)

    matched_old: set[int] = set()
    matched_new: set[int] = set()
    pairs: list[AlignedPair] = []

    # Greedy: pick highest-similarity pairs above threshold
    flat = [
        (sim[i][j], i, j)
        for i in range(len(new_paragraphs))
        for j in range(len(old_paragraphs))
    ]
    flat.sort(reverse=True)

    for score, ni, oi in flat:
        if score < match_threshold:
            break
        if ni in matched_new or oi in matched_old:
            continue
        matched_new.add(ni)
        matched_old.add(oi)

        change_type = "unchanged" if score >= unchanged_threshold else "revised"
        pair = AlignedPair(
            change_type=change_type,
            new_text=new_paragraphs[ni],
            old_text=old_paragraphs[oi],
            similarity=score,
        )
        if change_type == "revised":
            pair.added_words, pair.removed_words = _word_diff(
                old_paragraphs[oi], new_paragraphs[ni]
            )
        pairs.append(pair)

    # Unmatched new → added
    for ni in range(len(new_paragraphs)):
        if ni not in matched_new:
            pair = AlignedPair(
                change_type="added",
                new_text=new_paragraphs[ni],
                similarity=0.0,
            )
            pair.added_words = new_paragraphs[ni].split()
            pairs.append(pair)

    # Unmatched old → removed
    for oi in range(len(old_paragraphs)):
        if oi not in matched_old:
            pairs.append(AlignedPair(
                change_type="removed",
                old_text=old_paragraphs[oi],
                similarity=0.0,
                removed_words=old_paragraphs[oi].split(),
            ))

    return pairs


def _word_diff(old: str, new: str) -> tuple[list[str], list[str]]:
    """Return (added_words, removed_words) between old and new text."""
    old_words = old.split()
    new_words = new.split()
    sm = difflib.SequenceMatcher(None, old_words, new_words)

    added, removed = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            removed.extend(old_words[i1:i2])
        if tag in ("replace", "insert"):
            added.extend(new_words[j1:j2])
    return added, removed


def diff_sections(
    new_sections: dict[str, str],
    old_sections: dict[str, str],
    section_segmenter_module=None,
) -> dict[str, list[AlignedPair]]:
    """
    Run paragraph alignment for every item that appears in new_sections.
    Returns {item: [AlignedPair, ...]}.
    """
    from section_segmenter import split_paragraphs

    results: dict[str, list[AlignedPair]] = {}
    for item, new_text in new_sections.items():
        new_paras = split_paragraphs(new_text)
        old_paras = split_paragraphs(old_sections.get(item, ""))
        results[item] = align_paragraphs(new_paras, old_paras)
    return results
