"""Pre-generated AI analysis with Claude Opus 5.5 (runs in the scheduled GitHub Action).

For every exported diff (diffs/{accession}.json) that has no analysis yet, ask the model for
a short, cited summary of what changed and write ai/{accession}.json. The site is static,
so the API key never reaches the browser: it lives in the Action's secrets.

Spending is capped per run (--budget-usd, --max-filings); the run stops before the next
call once the cap is reached. Without ANTHROPIC_API_KEY the step is skipped.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib

log = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
PRICE_IN, PRICE_OUT = 4.0 / 1e6, 20.0 / 1e6        # USD per token, Opus 5.5 list price
MAX_INPUT_CHARS = 140_000                          # about 35k tokens of changed text per filing
SECTION_NAMES = {"risk_factors": "Risk Factors", "mdna": "MD&A", "market_risk": "Market Risk",
                 "financial_statements": "Financial Statements"}

SYSTEM = """You are an equity research analyst reading the changes between two consecutive SEC filings from the same company.
You receive only the paragraphs that were added, reworded or removed, each tagged with an id like risk_factors#12.
Rules:
- Use only the provided passages. Do not add outside facts, prices or forecasts.
- Every key change must cite the id of the passage it comes from.
- Prefer substance (new risks, guidance, legal matters, customers, supply, capital) over wording or number-only updates.
- Write plainly for a professional reader. No investment advice and no buy or sell language."""

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "One sentence, the single most important change."},
        "summary": {"type": "string", "description": "Two or three sentences on what changed overall."},
        "key_changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cite": {"type": "string", "description": "Passage id, e.g. risk_factors#12"},
                    "kind": {"type": "string", "enum": ["added", "changed", "removed"]},
                    "title": {"type": "string", "description": "Five to eight words."},
                    "why_it_matters": {"type": "string", "description": "One or two sentences."},
                },
                "required": ["cite", "kind", "title", "why_it_matters"],
                "additionalProperties": False,
            },
        },
        "tone": {"type": "string", "description": "One sentence on any shift in tone or hedging, or 'No clear shift.'"},
        "watch": {"type": "array", "items": {"type": "string"}, "description": "Up to three things to watch in the next filing."},
    },
    "required": ["headline", "summary", "key_changes", "tone", "watch"],
    "additionalProperties": False,
}


def build_prompt(diff: dict, company: str) -> str:
    lines = [f"Company: {company}", f"Filing: {diff['form']} filed {diff['filing_date']} "
             f"(accession {diff['accession']}), compared with the previous {diff['form']} filed {diff.get('prev_filing_date')}.", ""]
    used = sum(len(x) for x in lines)
    for sec in diff["sections"]:
        name = SECTION_NAMES.get(sec["key"], sec["title"])
        c = sec["counts"]
        lines.append(f"## {name}  ({c['added']} added, {c['changed']} reworded, {c['removed']} removed, {c['same']} unchanged)")
        for i, e in enumerate(sec["entries"]):
            if e["t"] == "same":
                continue
            pid = f"{sec['key']}#{i}"
            if e["t"] == "changed":
                block = f"[{pid} REWORDED]\nBEFORE: {e['before']}\nAFTER: {e['after']}"
            else:
                block = f"[{pid} {e['t'].upper()}]\n{e['text']}"
            if used + len(block) > MAX_INPUT_CHARS:
                lines.append("[remaining changes omitted for length]")
                return "\n\n".join(lines)
            lines.append(block)
            used += len(block)
    return "\n\n".join(lines)


def summarize_diff(client, diff: dict, company: str) -> tuple[dict | None, float, str]:
    """Returns (analysis or None, cost in USD, status)."""
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",                      # re-run on a fallback model if this one declines
        system=SYSTEM,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": build_prompt(diff, company)}],
    )
    u = response.usage
    cost = (u.input_tokens or 0) * PRICE_IN + (u.output_tokens or 0) * PRICE_OUT
    if response.stop_reason == "refusal":
        return None, cost, "refused"
    if response.stop_reason == "max_tokens":
        return None, cost, "truncated"
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, cost, "bad json"
    data.update({"model": response.model, "accession": diff["accession"], "compared_to": diff["compared_to"],
                 "input_tokens": u.input_tokens, "output_tokens": u.output_tokens})
    return data, cost, "ok"


def run(out_dir: str | pathlib.Path, max_filings: int = 10, budget_usd: float = 2.0, client=None) -> dict:
    out = pathlib.Path(out_dir)
    report = {"written": [], "skipped": [], "spent_usd": 0.0, "status": "ok"}
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            report["status"] = "no ANTHROPIC_API_KEY; skipped"
            return report
        import anthropic
        client = anthropic.Anthropic()
    import anthropic

    (out / "ai").mkdir(parents=True, exist_ok=True)
    index = json.loads((out / "index.json").read_text())
    todo = []
    for c in index["companies"]:
        feed = json.loads((out / c["feed"]).read_text())
        for f in feed["filings"]:
            if f.get("diff") and not (out / "ai" / f"{f['accession']}.json").exists():
                todo.append((f["filing_date"], f["accession"], f["diff"], feed["company"]["name"]))
    todo.sort(reverse=True)                        # newest filings first
    for _, acc, diff_path, company in todo[:max_filings]:
        if report["spent_usd"] >= budget_usd:
            report["status"] = f"budget of ${budget_usd:.2f} reached"
            break
        diff = json.loads((out / diff_path).read_text())
        try:
            data, cost, status = summarize_diff(client, diff, company)
        except anthropic.RateLimitError:
            report["status"] = "rate limited; stopping"
            break
        except anthropic.APIStatusError as exc:
            report["skipped"].append((acc, f"API error {exc.status_code}"))
            continue
        except anthropic.APIConnectionError:
            report["status"] = "network error; stopping"
            break
        report["spent_usd"] += cost
        if data is None:
            report["skipped"].append((acc, status))
            continue
        (out / "ai" / f"{acc}.json").write_text(json.dumps(data, ensure_ascii=True, indent=1), encoding="ascii")
        report["written"].append(acc)
    report["spent_usd"] = round(report["spent_usd"], 4)
    return report
