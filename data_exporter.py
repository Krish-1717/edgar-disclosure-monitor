"""
data_exporter.py — Export alerts, news rankings, and backtest results.

Supports CSV, JSON, and Excel (openpyxl). Produces timestamped files with
optional summary sheets and can bundle multiple exports into a ZIP archive.

Usage:
    exporter = DataExporter(output_dir=Path("exports"))
    exporter.export_alerts(alerts, fmt=ExportFormat.EXCEL)
    exporter.export_all(alerts, news, backtest_result)
"""

from __future__ import annotations

import csv
import json
import zipfile
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class ExportFormat(Enum):
    CSV   = "csv"
    JSON  = "json"
    EXCEL = "xlsx"


# ---------------------------------------------------------------------------
# Column definitions per data type
# ---------------------------------------------------------------------------

ALERT_COLUMNS = [
    "ticker", "form_type", "score", "priority", "filing_date",
    "summary", "filing_url", "alert_id",
]

NEWS_COLUMNS = [
    "rank", "title", "source", "published_at", "final_score",
    "relevance_score", "authority_score", "recency_score",
    "keyword_boost", "matched_keywords", "url",
]

BACKTEST_COLUMNS = [
    "source", "tier", "valid", "reason", "checked_at",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _flatten(obj) -> dict:
    """Convert dataclass or dict to flat dict."""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return dict(obj)


def _cell_value(v) -> str:
    """Stringify a value for CSV/Excel cells."""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    if v is None:
        return ""
    return str(v)


# ---------------------------------------------------------------------------
# Excel writer (openpyxl)
# ---------------------------------------------------------------------------

def _write_excel(rows: list, columns: list, sheet_name: str, path: Path,
                 title: str = "") -> None:
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise ImportError("openpyxl is required for Excel export. pip install openpyxl")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name

    header_font  = Font(bold=True, color="FFFFFF", size=11)
    header_fill  = PatternFill("solid", fgColor="1C2128")
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Title row
    if title:
        ws.append([title])
        ws["A1"].font = Font(bold=True, size=13, color="E6EDF3")
        ws.merge_cells(f"A1:{get_column_letter(len(columns))}1")
        ws.row_dimensions[1].height = 22

    # Header row
    header_row = 2 if title else 1
    ws.append(columns)
    for col_idx, _ in enumerate(columns, 1):
        cell = ws.cell(row=header_row, column=col_idx)
        cell.font  = header_font
        cell.fill  = header_fill
        cell.alignment = center_align

    # Data rows
    for row in rows:
        flat = _flatten(row)
        ws.append([_cell_value(flat.get(col, "")) for col in columns])

    # Auto-width columns
    for col_idx, col_name in enumerate(columns, 1):
        col_letter = get_column_letter(col_idx)
        max_len = max(
            len(col_name),
            max((len(_cell_value(_flatten(r).get(col_name, ""))) for r in rows), default=0),
        )
        ws.column_dimensions[col_letter].width = min(max_len + 4, 60)

    ws.freeze_panes = f"A{header_row + 1}"
    wb.save(path)


# ---------------------------------------------------------------------------
# DataExporter
# ---------------------------------------------------------------------------

class DataExporter:
    """
    Exports alerts, news rankings, and backtest results in CSV, JSON, or Excel.

    All output files are timestamped and saved to output_dir.
    """

    def __init__(self, output_dir: Path = Path("exports")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str, fmt: ExportFormat) -> Path:
        return self.output_dir / f"{name}_{_ts()}.{fmt.value}"

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def export_alerts(
        self,
        alerts: list,
        fmt: ExportFormat = ExportFormat.CSV,
        filename: Optional[str] = None,
    ) -> Path:
        """Export a list of alert dicts or Alert objects."""
        rows = [_flatten(a) for a in alerts]
        path = self._path(filename or "alerts", fmt)

        if fmt == ExportFormat.CSV:
            self._write_csv(rows, ALERT_COLUMNS, path)
        elif fmt == ExportFormat.JSON:
            self._write_json(rows, path, key="alerts")
        elif fmt == ExportFormat.EXCEL:
            _write_excel(rows, ALERT_COLUMNS, "Alerts", path,
                         title=f"EDGAR Alerts — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        return path

    # ------------------------------------------------------------------
    # News rankings
    # ------------------------------------------------------------------

    def export_news(
        self,
        articles: list,
        fmt: ExportFormat = ExportFormat.CSV,
        filename: Optional[str] = None,
    ) -> Path:
        """Export RankedArticle objects or dicts."""
        rows = []
        for i, a in enumerate(articles, 1):
            flat = _flatten(a)
            flat.setdefault("rank", i)
            rows.append(flat)
        path = self._path(filename or "news_rankings", fmt)

        if fmt == ExportFormat.CSV:
            self._write_csv(rows, NEWS_COLUMNS, path)
        elif fmt == ExportFormat.JSON:
            self._write_json(rows, path, key="news")
        elif fmt == ExportFormat.EXCEL:
            _write_excel(rows, NEWS_COLUMNS, "News Rankings", path,
                         title=f"News Relevance Rankings — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        return path

    # ------------------------------------------------------------------
    # Backtest results
    # ------------------------------------------------------------------

    def export_backtest(
        self,
        backtest_result,
        fmt: ExportFormat = ExportFormat.CSV,
        filename: Optional[str] = None,
    ) -> Path:
        """Export BacktestResult object or dict."""
        flat = _flatten(backtest_result)
        # Expand source_results list if present
        rows = flat.get("source_results", [flat])
        if not isinstance(rows, list):
            rows = [flat]
        rows = [_flatten(r) for r in rows]
        path = self._path(filename or "backtest_results", fmt)

        if fmt == ExportFormat.CSV:
            cols = BACKTEST_COLUMNS if rows else []
            self._write_csv(rows, cols, path)
        elif fmt == ExportFormat.JSON:
            self._write_json(flat, path, key="backtest")
        elif fmt == ExportFormat.EXCEL:
            _write_excel(rows, BACKTEST_COLUMNS, "Backtest", path,
                         title=f"News Backtest Results — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        return path

    # ------------------------------------------------------------------
    # Combined export
    # ------------------------------------------------------------------

    def export_all(
        self,
        alerts: list,
        news: list,
        backtest_result=None,
        fmt: ExportFormat = ExportFormat.EXCEL,
        zip_output: bool = False,
    ) -> list:
        """
        Export all data types. If fmt=EXCEL and zip_output=False, produces
        separate files. If zip_output=True, bundles them in a ZIP.
        Returns list of output paths.
        """
        paths = [
            self.export_alerts(alerts, fmt=fmt),
            self.export_news(news, fmt=fmt),
        ]
        if backtest_result is not None:
            paths.append(self.export_backtest(backtest_result, fmt=fmt))

        if zip_output:
            zip_path = self.output_dir / f"edgar_export_{_ts()}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in paths:
                    zf.write(p, p.name)
            # Remove individual files
            for p in paths:
                p.unlink(missing_ok=True)
            return [zip_path]

        return paths

    # ------------------------------------------------------------------
    # Low-level writers
    # ------------------------------------------------------------------

    def _write_csv(self, rows: list, columns: list, path: Path) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=columns, extrasaction="ignore"
            )
            writer.writeheader()
            for row in rows:
                writer.writerow({col: _cell_value(row.get(col, "")) for col in columns})

    def _write_json(self, data, path: Path, key: str = "data") -> None:
        wrapper = {
            key: data,
            "exported_at": datetime.utcnow().isoformat(),
            "count": len(data) if isinstance(data, list) else 1,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(wrapper, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    exporter = DataExporter(output_dir=Path("exports/demo"))

    sample_alerts = [
        {"ticker": "NVDA", "form_type": "8-K", "score": 0.85,
         "priority": "HIGH", "filing_date": "2026-10-01",
         "summary": "Earnings beat; guidance raised", "filing_url": "https://sec.gov/1",
         "alert_id": "a001"},
        {"ticker": "SVB",  "form_type": "10-K", "score": 0.97,
         "priority": "CRITICAL", "filing_date": "2026-09-15",
         "summary": "Going concern doubt expressed by auditors", "filing_url": "https://sec.gov/2",
         "alert_id": "a002"},
    ]

    sample_news = [
        {"rank": 1, "title": "Fed raises rates", "source": "wsj",
         "published_at": "2026-10-01T10:00:00", "final_score": 0.92,
         "relevance_score": 0.85, "authority_score": 1.0, "recency_score": 0.95,
         "keyword_boost": 1.4, "matched_keywords": ["rate hike"],
         "url": "https://wsj.com/1"},
    ]

    csv_path  = exporter.export_alerts(sample_alerts, fmt=ExportFormat.CSV)
    json_path = exporter.export_news(sample_news, fmt=ExportFormat.JSON)
    print(f"CSV alerts → {csv_path}")
    print(f"JSON news  → {json_path}")
