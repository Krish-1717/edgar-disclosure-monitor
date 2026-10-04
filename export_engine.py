"""
export_engine.py — CSV and PDF Export for EDGAR Disclosure Monitor

Exports alerts, diffs, and watchlist data to shareable formats.

Functions:
  export_alerts_csv(conn, path, min_rank)   → alerts.csv
  export_diff_csv(conn, alert_id, path)     → diff for one alert
  export_watchlist_csv(conn, path)          → watchlist overview
  export_alert_pdf(conn, alert_id, path)    → PDF report for one alert
  export_weekly_report_pdf(conn, path)      → full weekly digest PDF

Usage:
    from export_engine import export_alerts_csv, export_alert_pdf
    export_alerts_csv(conn, "data/exports/alerts.csv", min_rank=3)
    export_alert_pdf(conn, alert_id=42, path="data/exports/alert_42.pdf")

CLI:
    python export_engine.py --type alerts --min-rank 3 --output exports/
    python export_engine.py --type diff   --alert-id 42
    python export_engine.py --type pdf    --alert-id 42
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import logging
import pathlib
import sqlite3
import textwrap
from datetime import date, datetime
from typing import Optional

log = logging.getLogger(__name__)

RANK_LABELS = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "MINIMAL"}
RANK_COLORS_HEX = {5: "#ef5350", 4: "#ffa726", 3: "#ffee58", 2: "#26c6da", 1: "#9e9e9e"}


# ── CSV Exports ────────────────────────────────────────────────────────────────

def export_alerts_csv(
    conn: sqlite3.Connection,
    path: pathlib.Path | str = "data/exports/alerts.csv",
    min_rank: int = 1,
) -> pathlib.Path:
    """
    Export all alerts to a CSV file.
    Columns: Ticker, Form, Filed, Period, Rank, RankLabel, Materiality, Burial, AttentionGap, TopSections
    """
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = conn.execute("""
        SELECT a.*, f.form FROM alerts a
        JOIN filings f ON a.new_filing_id = f.id
        WHERE a.ranking >= ?
        ORDER BY a.attention_gap DESC
    """, (min_rank,)).fetchall()

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "Ticker", "Form", "Filed", "Period", "Rank", "RankLabel",
            "Materiality", "Burial", "AttentionGap",
            "FilingDayReturn", "AbnormalReturn", "VolumeRatio",
            "TopSections", "CreatedAt",
        ])
        for r in rows:
            summary = json.loads(r["summary_items"] or "[]")
            top_secs = "; ".join(f"Item {s['item']} ({s['score']:.1f})" for s in summary[:3])
            writer.writerow([
                r["ticker"],
                r.get("form") or "",
                r["filed"],
                r.get("period") or "",
                r["ranking"],
                RANK_LABELS.get(r["ranking"], ""),
                round(r["materiality_score"], 2),
                round(r["burial_score"], 2),
                round(r["attention_gap"], 2),
                r["filing_day_return"]   if "filing_day_return"   in r.keys() else "",
                r["abnormal_return"]     if "abnormal_return"     in r.keys() else "",
                r["volume_ratio"]        if "volume_ratio"        in r.keys() else "",
                top_secs,
                r.get("created_at") or "",
            ])

    log.info("Exported %d alerts to %s", len(rows), path)
    return path


def export_diff_csv(
    conn: sqlite3.Connection,
    alert_id: int,
    path: Optional[pathlib.Path | str] = None,
) -> pathlib.Path:
    """
    Export paragraph-level changes for a single alert to CSV.
    """
    alert = conn.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
    if not alert:
        raise ValueError(f"Alert {alert_id} not found")

    if path is None:
        path = pathlib.Path(f"data/exports/diff_{alert['ticker']}_{alert['filed']}_{alert_id}.csv")
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    changes = conn.execute("""
        SELECT item, change_type, new_text, old_text, similarity,
               word_delta, added_words, removed_words,
               llm_topic, llm_summary, llm_severity, llm_quote
        FROM changes
        WHERE new_filing_id = ? AND change_type != 'unchanged'
        ORDER BY item, rowid
    """, (alert["new_filing_id"],)).fetchall()

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "Item", "ChangeType", "Similarity", "WordDelta",
            "AddedWords", "RemovedWords",
            "LLM_Topic", "LLM_Severity", "LLM_Summary", "LLM_Quote",
            "NewText", "OldText",
        ])
        for c in changes:
            writer.writerow([
                c["item"], c["change_type"],
                round(c["similarity"], 4) if c["similarity"] else "",
                c["word_delta"] or 0,
                c["added_words"] or 0, c["removed_words"] or 0,
                c.get("llm_topic") or "",
                c.get("llm_severity") or "",
                c.get("llm_summary") or "",
                c.get("llm_quote") or "",
                (c["new_text"] or "")[:2000],
                (c["old_text"] or "")[:2000],
            ])

    log.info("Exported %d changes for alert %d to %s", len(changes), alert_id, path)
    return path


def export_watchlist_csv(
    conn: sqlite3.Connection,
    path: pathlib.Path | str = "data/exports/watchlist.csv",
) -> pathlib.Path:
    """Export the full watchlist with stats."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = conn.execute("""
        SELECT c.ticker, c.name, c.sector,
               COUNT(DISTINCT f.id)               AS filings,
               MAX(f.filed)                       AS last_filed,
               COUNT(DISTINCT a.id)               AS alerts,
               ROUND(AVG(a.materiality_score),1)  AS avg_materiality,
               MAX(a.ranking)                     AS max_rank
        FROM companies c
        LEFT JOIN filings f ON f.ticker = c.ticker AND f.fetched = 1
        LEFT JOIN alerts  a ON a.ticker = c.ticker
        GROUP BY c.ticker ORDER BY c.sector, c.ticker
    """).fetchall()

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Ticker", "Company", "Sector", "Filings", "LastFiled",
                         "Alerts", "AvgMateriality", "MaxRank"])
        for r in rows:
            writer.writerow([r["ticker"], r["name"], r["sector"],
                             r["filings"], r["last_filed"] or "",
                             r["alerts"], r["avg_materiality"] or "",
                             RANK_LABELS.get(r["max_rank"], "") if r["max_rank"] else ""])

    log.info("Exported watchlist (%d companies) to %s", len(rows), path)
    return path


# ── PDF Exports (reportlab) ────────────────────────────────────────────────────

def _check_reportlab() -> bool:
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        log.warning("reportlab not installed. Run: pip install reportlab")
        return False


def export_alert_pdf(
    conn: sqlite3.Connection,
    alert_id: int,
    path: Optional[pathlib.Path | str] = None,
) -> Optional[pathlib.Path]:
    """
    Generate a PDF report for a single alert.
    Requires: pip install reportlab
    """
    if not _check_reportlab():
        return None

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    alert = conn.execute("""
        SELECT a.*, f.form FROM alerts a
        JOIN filings f ON a.new_filing_id = f.id WHERE a.id=?
    """, (alert_id,)).fetchone()
    if not alert:
        raise ValueError(f"Alert {alert_id} not found")

    changes = conn.execute("""
        SELECT item, change_type, new_text, old_text, llm_topic, llm_summary, llm_severity
        FROM changes WHERE new_filing_id=? AND change_type != 'unchanged'
        ORDER BY item, rowid LIMIT 50
    """, (alert["new_filing_id"],)).fetchall()

    if path is None:
        path = pathlib.Path(f"data/exports/alert_{alert['ticker']}_{alert['filed']}_{alert_id}.pdf")
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            rightMargin=inch * 0.75, leftMargin=inch * 0.75,
                            topMargin=inch * 0.75, bottomMargin=inch * 0.75)

    styles = getSampleStyleSheet()
    h1  = ParagraphStyle("h1",  parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#1a1a2e"))
    h2  = ParagraphStyle("h2",  parent=styles["Heading2"], fontSize=13, textColor=colors.HexColor("#16213e"), spaceAfter=4)
    bod = ParagraphStyle("bod", parent=styles["Normal"],   fontSize=9,  leading=13, textColor=colors.HexColor("#333"))
    sm  = ParagraphStyle("sm",  parent=styles["Normal"],   fontSize=8,  leading=11, textColor=colors.HexColor("#666"))
    rank_color = colors.HexColor(RANK_COLORS_HEX.get(alert["ranking"], "#9e9e9e"))

    story = []

    # Header
    story.append(Paragraph(f"EDGAR Alert Report — {alert['ticker']}", h1))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"{alert.get('form','10-K/Q')} filed {alert['filed']} · Period: {alert.get('period','—')}", sm))
    story.append(Spacer(1, 12))

    # KPI table
    kpi_data = [
        ["Rank", "Materiality", "Burial Score", "Attention Gap"],
        [
            RANK_LABELS.get(alert["ranking"], "—"),
            f"{alert['materiality_score']:.1f}/100",
            f"{alert['burial_score']:.1f}/100",
            f"{alert['attention_gap']:.1f}",
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[1.5 * inch] * 4)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#f0f4f8")),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 9),
        ("FONTNAME",    (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 1), (-1, 1), 12),
        ("TEXTCOLOR",   (0, 1), (0, 1), rank_color),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#dde")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#ccd")))
    story.append(Spacer(1, 12))

    # Changes
    story.append(Paragraph("Changed Paragraphs", h2))
    for c in changes:
        topic    = c.get("llm_topic") or "—"
        severity = c.get("llm_severity") or ""
        summary  = c.get("llm_summary") or ""
        change_label = {
            "added":   "➕ Added",
            "removed": "➖ Removed",
            "revised": "✏ Revised",
        }.get(c["change_type"], c["change_type"])

        story.append(Paragraph(
            f"Item {c['item']} &nbsp;·&nbsp; {change_label}"
            + (f" &nbsp;·&nbsp; <font color='gray'>{topic}</font>" if topic != "—" else "")
            + (f" &nbsp;·&nbsp; <b>{severity}</b>" if severity else ""),
            h2,
        ))
        if summary:
            story.append(Paragraph(f"<i>{summary}</i>", sm))
            story.append(Spacer(1, 4))

        if c["new_text"]:
            txt = textwrap.shorten(c["new_text"], width=600, placeholder="…")
            story.append(Paragraph(f"<b>New:</b> {txt}", bod))
        if c["old_text"] and c["change_type"] == "revised":
            txt = textwrap.shorten(c["old_text"], width=300, placeholder="…")
            story.append(Paragraph(f"<b>Prior:</b> {txt}", sm))
        story.append(Spacer(1, 8))

    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#ccd")))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"Generated by EDGAR Disclosure Monitor · {date.today().isoformat()} · "
        "github.com/Krish-1717/edgar-disclosure-monitor",
        sm,
    ))

    doc.build(story)
    log.info("PDF exported to %s (%d changes)", path, len(changes))
    return path


def export_weekly_report_pdf(
    conn: sqlite3.Connection,
    path: pathlib.Path | str = "data/exports/weekly_report.pdf",
    min_rank: int = 3,
) -> Optional[pathlib.Path]:
    """
    Generate a full weekly digest PDF with all significant alerts.
    Requires: pip install reportlab
    """
    if not _check_reportlab():
        return None

    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    alerts = conn.execute("""
        SELECT a.ticker, f.form, a.filed, a.period, a.ranking,
               a.materiality_score, a.burial_score, a.attention_gap, a.summary_items
        FROM alerts a JOIN filings f ON a.new_filing_id = f.id
        WHERE a.ranking >= ?
        ORDER BY a.attention_gap DESC LIMIT 100
    """, (min_rank,)).fetchall()

    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            rightMargin=inch * 0.75, leftMargin=inch * 0.75,
                            topMargin=inch * 0.75, bottomMargin=inch * 0.75)

    styles = getSampleStyleSheet()
    h1  = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20)
    sm  = ParagraphStyle("sm", parent=styles["Normal"],   fontSize=8, textColor=colors.gray)

    story = [
        Paragraph(f"EDGAR Weekly Alert Digest — {date.today().isoformat()}", h1),
        Spacer(1, 12),
        Paragraph(f"{len(alerts)} alerts (rank ≥ {RANK_LABELS.get(min_rank, str(min_rank))})", sm),
        Spacer(1, 16),
    ]

    table_data = [["Ticker", "Form", "Filed", "Rank", "Materiality", "Burial", "Gap"]]
    for a in alerts:
        table_data.append([
            a["ticker"], a.get("form") or "", a["filed"],
            RANK_LABELS.get(a["ranking"], ""),
            f"{a['materiality_score']:.1f}", f"{a['burial_score']:.1f}",
            f"{a['attention_gap']:.1f}",
        ])

    tbl = Table(table_data, colWidths=[0.7, 0.7, 0.85, 0.85, 0.85, 0.7, 0.7])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 8),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#dde")),
        ("ROWBACKGROUNDS", (1, 0), (-1, -1), [colors.white, colors.HexColor("#f7f7fb")]),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "EDGAR Disclosure Monitor · github.com/Krish-1717/edgar-disclosure-monitor", sm
    ))

    doc.build(story)
    log.info("Weekly report PDF exported: %d alerts → %s", len(alerts), path)
    return path


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Export EDGAR data")
    parser.add_argument("--type",      required=True, choices=["alerts", "diff", "watchlist", "pdf", "weekly-pdf"])
    parser.add_argument("--alert-id",  type=int, help="Alert ID (for diff/pdf)")
    parser.add_argument("--min-rank",  type=int, default=1)
    parser.add_argument("--output",    default="data/exports/", help="Output directory")
    args = parser.parse_args()

    from database import get_connection, init_db
    conn = get_connection()
    init_db(conn)
    out = pathlib.Path(args.output)

    if args.type == "alerts":
        export_alerts_csv(conn, out / "alerts.csv", min_rank=args.min_rank)
    elif args.type == "diff":
        if not args.alert_id:
            parser.error("--alert-id required for diff export")
        export_diff_csv(conn, args.alert_id, out / f"diff_{args.alert_id}.csv")
    elif args.type == "watchlist":
        export_watchlist_csv(conn, out / "watchlist.csv")
    elif args.type == "pdf":
        if not args.alert_id:
            parser.error("--alert-id required for pdf export")
        p = export_alert_pdf(conn, args.alert_id, out / f"alert_{args.alert_id}.pdf")
        if not p:
            print("Install reportlab: pip install reportlab")
    elif args.type == "weekly-pdf":
        p = export_weekly_report_pdf(conn, out / "weekly_report.pdf", min_rank=args.min_rank)
        if not p:
            print("Install reportlab: pip install reportlab")
