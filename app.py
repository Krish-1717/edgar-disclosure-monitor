"""
app.py — EDGAR Disclosure Monitor (Streamlit UI)

Three views:
  1. Watchlist    — companies being monitored, recent filings
  2. Alert Feed   — ranked by Attention Gap, filterable by ticker/rank
  3. Diff Viewer  — side-by-side section diff for any alert
"""
from __future__ import annotations
import json
import pathlib
import streamlit as st
import pandas as pd

from database import get_connection, init_db, get_alerts

DB_PATH = pathlib.Path("data/edgar.db")

st.set_page_config(
    page_title="EDGAR Disclosure Monitor",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="metric-container"] {
    background: var(--secondary-background-color);
    border: 1px solid var(--border-color, #2d3748);
    border-radius: 10px;
    padding: 12px 16px;
}
.rank-5 { color: #ef5350; font-weight: 700; }
.rank-4 { color: #ffa726; font-weight: 700; }
.rank-3 { color: #ffee58; font-weight: 600; }
.rank-2 { color: #26c6da; }
.rank-1 { color: #9e9e9e; }
.diff-added   { background: rgba(38,198,218,0.15); border-left: 3px solid #26c6da; padding: 6px 10px; margin: 4px 0; border-radius: 4px; }
.diff-removed { background: rgba(239,83,80,0.12);  border-left: 3px solid #ef5350; padding: 6px 10px; margin: 4px 0; border-radius: 4px; }
.diff-revised { background: rgba(255,167,38,0.12); border-left: 3px solid #ffa726; padding: 6px 10px; margin: 4px 0; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def _conn():
    conn = get_connection(DB_PATH)
    init_db(conn)
    return conn


conn = _conn()

RANK_LABELS = {5: "🔴 CRITICAL", 4: "🟠 HIGH", 3: "🟡 MEDIUM", 2: "🔵 LOW", 1: "⚪ MINIMAL"}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 EDGAR Monitor")
    st.markdown("---")
    view = st.radio("View", ["Alert Feed", "Watchlist", "Diff Viewer"], key="view")
    st.markdown("---")

    tickers_in_db = [
        r[0] for r in conn.execute("SELECT DISTINCT ticker FROM companies ORDER BY ticker").fetchall()
    ]
    filter_ticker = st.selectbox("Filter by company", ["All"] + tickers_in_db, key="filter_ticker")
    filter_rank   = st.multiselect("Min rank", [5, 4, 3, 2, 1], default=[5, 4, 3], key="filter_rank")

    st.markdown("---")
    st.caption("Run `python run_pipeline.py --all` to ingest filings.")


# ── Alert Feed ────────────────────────────────────────────────────────────────
if view == "Alert Feed":
    st.markdown("## 📊 Alert Feed")
    st.markdown("Ranked by **Attention Gap** — high materiality changes with low press coverage surface first.")

    ticker_arg = None if filter_ticker == "All" else filter_ticker
    alerts = get_alerts(conn, ticker=ticker_arg, limit=200)

    if not alerts:
        st.info("No alerts yet. Run the pipeline to ingest filings: `python run_pipeline.py --all`")
        st.stop()

    rows = []
    for a in alerts:
        if filter_rank and a["ranking"] not in filter_rank:
            continue
        summary = json.loads(a["summary_items"] or "[]")
        top_item = summary[0]["item"] if summary else "—"
        rows.append({
            "Ticker":       a["ticker"],
            "Form":         a["form"],
            "Filed":        a["filed"],
            "Period":       a["period"],
            "Rank":         RANK_LABELS.get(a["ranking"], "—"),
            "Materiality":  round(a["materiality_score"], 1),
            "Burial":       round(a["burial_score"], 1),
            "Attention Gap": round(a["attention_gap"], 1),
            "Top Section":  f"Item {top_item}",
            "_alert_id":    a["id"],
        })

    if not rows:
        st.info("No alerts match the current filters.")
        st.stop()

    df = pd.DataFrame(rows)
    display_cols = [c for c in df.columns if not c.startswith("_")]

    # KPI row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Alerts",   len(df))
    col2.metric("Critical / High", len(df[df["Rank"].str.contains("CRITICAL|HIGH")]))
    col3.metric("Avg Materiality", f"{df['Materiality'].mean():.1f}")
    col4.metric("Avg Attention Gap", f"{df['Attention Gap'].mean():.1f}")

    st.markdown("---")
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

    # Select alert for detail view
    if rows:
        st.markdown("### Alert Detail")
        selected_idx = st.selectbox(
            "Select alert to inspect",
            range(len(rows)),
            format_func=lambda i: f"{rows[i]['Ticker']}  {rows[i]['Form']}  {rows[i]['Filed']}  {rows[i]['Rank']}",
            key="selected_alert",
        )
        alert_row = rows[selected_idx]
        alert_id  = alert_row["_alert_id"]

        alert_db = conn.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
        if alert_db:
            summary_items = json.loads(alert_db["summary_items"] or "[]")
            st.markdown(f"**{alert_row['Ticker']}** — {alert_row['Form']} filed {alert_row['Filed']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Materiality", f"{alert_db['materiality_score']:.1f}/100")
            c2.metric("Burial Score", f"{alert_db['burial_score']:.1f}/100")
            c3.metric("Attention Gap", f"{alert_db['attention_gap']:.1f}")
            c4.metric("Ranking", RANK_LABELS.get(alert_db["ranking"], "—"))

            if summary_items:
                st.markdown("**Top changed sections:**")
                for s in summary_items:
                    st.markdown(f"- Item **{s['item']}** — materiality score {s['score']:.1f}")

            if st.button("Open in Diff Viewer →"):
                st.session_state["diff_new_id"]  = alert_db["new_filing_id"]
                st.session_state["diff_old_id"]  = alert_db["old_filing_id"]
                st.session_state["view"]          = "Diff Viewer"
                st.rerun()


# ── Watchlist ─────────────────────────────────────────────────────────────────
elif view == "Watchlist":
    st.markdown("## 🏢 Watchlist")

    companies = conn.execute("""
        SELECT c.ticker, c.name, c.sector,
               COUNT(DISTINCT f.id) AS n_filings,
               MAX(f.filed)         AS last_filed,
               COUNT(DISTINCT a.id) AS n_alerts
        FROM companies c
        LEFT JOIN filings f ON f.ticker = c.ticker
        LEFT JOIN alerts  a ON a.ticker = c.ticker
        GROUP BY c.ticker
        ORDER BY c.sector, c.ticker
    """).fetchall()

    if not companies:
        st.info("No companies in the database yet. Run the pipeline first.")
        st.stop()

    df_co = pd.DataFrame([dict(r) for r in companies])
    df_co.columns = ["Ticker", "Company", "Sector", "Filings Ingested", "Last Filed", "Alerts"]
    st.dataframe(df_co, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("**Coverage by sector:**")
    sector_counts = df_co.groupby("Sector")["Ticker"].count()
    st.bar_chart(sector_counts)


# ── Diff Viewer ───────────────────────────────────────────────────────────────
elif view == "Diff Viewer":
    st.markdown("## 🔍 Side-by-Side Diff Viewer")

    new_id = st.session_state.get("diff_new_id")
    old_id = st.session_state.get("diff_old_id")

    if not new_id or not old_id:
        st.info("Select an alert from the Alert Feed and click 'Open in Diff Viewer'.")
        st.stop()

    new_filing = conn.execute("SELECT * FROM filings WHERE id=?", (new_id,)).fetchone()
    old_filing = conn.execute("SELECT * FROM filings WHERE id=?", (old_id,)).fetchone()

    if not new_filing or not old_filing:
        st.error("Filing not found in database.")
        st.stop()

    st.markdown(
        f"**{new_filing['ticker']}** &nbsp;|&nbsp; "
        f"New: {new_filing['form']} {new_filing['filed']} &nbsp;→&nbsp; "
        f"Prior: {old_filing['form']} {old_filing['filed']}"
    )

    # Get all changed paragraphs for these two filings
    changes = conn.execute("""
        SELECT * FROM changes
        WHERE new_filing_id=? AND old_filing_id=?
        AND change_type != 'unchanged'
        ORDER BY item, rowid
    """, (new_id, old_id)).fetchall()

    if not changes:
        st.info("No significant changes found between these filings.")
        st.stop()

    items = sorted(set(r["item"] for r in changes))
    selected_item = st.selectbox("Item / Section", items, key="diff_item",
                                  format_func=lambda x: f"Item {x}")

    item_changes = [r for r in changes if r["item"] == selected_item]

    added   = [r for r in item_changes if r["change_type"] == "added"]
    removed = [r for r in item_changes if r["change_type"] == "removed"]
    revised = [r for r in item_changes if r["change_type"] == "revised"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Added",   len(added))
    c2.metric("Revised", len(revised))
    c3.metric("Removed", len(removed))

    st.markdown("---")

    col_new, col_old = st.columns(2)
    col_new.markdown(f"#### New Filing ({new_filing['filed']})")
    col_old.markdown(f"#### Prior Filing ({old_filing['filed']})")

    for r in revised[:20]:
        col_new.markdown(
            f'<div class="diff-revised">{r["new_text"][:600]}</div>',
            unsafe_allow_html=True,
        )
        col_old.markdown(
            f'<div class="diff-revised">{r["old_text"][:600]}</div>',
            unsafe_allow_html=True,
        )

    for r in added[:10]:
        col_new.markdown(
            f'<div class="diff-added">➕ {r["new_text"][:600]}</div>',
            unsafe_allow_html=True,
        )
        col_old.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

    for r in removed[:10]:
        col_new.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
        col_old.markdown(
            f'<div class="diff-removed">➖ {r["old_text"][:600]}</div>',
            unsafe_allow_html=True,
        )

    if len(item_changes) > 30:
        st.caption(f"Showing first 30 of {len(item_changes)} changed paragraphs.")
