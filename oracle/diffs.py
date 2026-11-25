"""Aligned, paragraph-level diffs for the side-by-side reader.

For one section of two filings (previous, current) this returns the paragraphs of the
current filing in document order, each tagged:

  same     wording unchanged (numbers may differ); text collapsed to a short preview
  changed  reworded; carries both versions plus word-level ops for highlighting
  added    new in the current filing
  removed  present before, gone now (placed after the paragraph it used to follow)

Matching uses the same word-overlap rule as the change score (export.section_change), so
the reader and the score always agree.
"""
from __future__ import annotations

import difflib
import re

from .export import MODIFIED_SIM, UNCHANGED_SIM, _best, _paragraphs, _tokens

PREVIEW_CHARS = 140
_WORD_RE = re.compile(r"\S+|\s+")


def _preview(p: str) -> str:
    return p if len(p) <= PREVIEW_CHARS else p[: PREVIEW_CHARS - 3].rsplit(" ", 1)[0] + "..."


def word_ops(before: str, after: str) -> list[list[str]]:
    """[[op, text], ...] with op in '=', '-', '+' over word tokens (whitespace kept)."""
    a, b = _WORD_RE.findall(before), _WORD_RE.findall(after)
    out: list[list[str]] = []

    def push(op: str, text: str) -> None:
        if not text:
            return
        if out and out[-1][0] == op:
            out[-1][1] += text
        else:
            out.append([op, text])

    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            push("=", "".join(a[i1:i2]))
        else:
            push("-", "".join(a[i1:i2]))
            push("+", "".join(b[j1:j2]))
    return out


def align_section(prev_text: str, cur_text: str) -> list[dict]:
    prev, cur = _paragraphs(prev_text), _paragraphs(cur_text)
    prev_tok, cur_tok = [_tokens(p) for p in prev], [_tokens(p) for p in cur]
    entries: list[dict] = []
    matched_prev: dict[int, int] = {}       # prev index -> entry index
    for p, tok in zip(cur, cur_tok):
        sim, j = _best(tok, prev_tok)
        if sim >= UNCHANGED_SIM:
            entries.append({"t": "same", "text": _preview(p), "full": len(p), "pi": j})
            matched_prev.setdefault(j, len(entries) - 1)
        elif sim >= MODIFIED_SIM:
            entries.append({"t": "changed", "before": prev[j], "after": p, "sim": round(sim, 2),
                            "ops": word_ops(prev[j], p), "pi": j})
            matched_prev.setdefault(j, len(entries) - 1)
        else:
            entries.append({"t": "added", "text": p})
    # removed paragraphs: those with no counterpart at >= MODIFIED_SIM
    removed = [j for j, tok in enumerate(prev_tok) if _best(tok, cur_tok)[0] < MODIFIED_SIM]
    for j in sorted(removed, reverse=True):
        anchor = max((k for k in matched_prev if k < j), default=None)
        pos = matched_prev[anchor] + 1 if anchor is not None else 0
        entries.insert(pos, {"t": "removed", "text": prev[j]})
        for k in matched_prev:
            if matched_prev[k] >= pos:
                matched_prev[k] += 1
    for e in entries:
        e.pop("pi", None)
    return entries


def summarize(entries: list[dict]) -> dict:
    c = {"same": 0, "changed": 0, "added": 0, "removed": 0}
    for e in entries:
        c[e["t"]] += 1
    return c
