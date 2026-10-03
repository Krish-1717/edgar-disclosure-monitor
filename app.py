"""
app.py — EDGAR Disclosure Monitor (Streamlit UI)

Three views:
  1. Alert Feed   — ranked by Attention Gap, filterable by ticker/rank
  2. Watchlist    — companies being monitored, filing counts by sector
  3. Diff Viewer  — side-by-side paragraph diff for any alert
"""
from __future__ import annotations
import json
import pathlib
import subprocess
import sys
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
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    padding: 12px 16px;
}
.rank-5 { color: #ef5350; font-weight: 700; font-size: 1.05em; }
.rank-4 { color: #ffa726; font-weight: 700; }
.rank-3 { color: #ffee58; font-weight: 600; }
.rank-2 { color: #26c6da; }
.rank-1 { color: #9e9e9e; }
.diff-added   {
    background: rgba(38,198,218,0.12);
    border-left: 3px solid #26c6da;
    padding: 8px 12px; margin: 4px 0; border-radius: 4px;
    font-size: 0.88em; line-height: 1.5;
}
.diff-removed {
    background: rgba(239,83,80,0.10);
    border-left: 3px solid #ef5350;
    padding: 8px 12px; margin: 4px 0; border-radius: 4px;
    font-size: 0.88em; line-height: 1.5;
}
.diff-revised {
    background: rgba(255,167,38,0.10);
    border-left: 3px solid #ffa726;
    padding: 8px 12px; margin: 4px 0; border-radius: 4px;
    font-size: 0.88em; line-height: 1.5;
}
.alert-card {
    background: var(--secondary-background-color);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 16px;
    margin: 8px 0;
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def _conn():
    conn = get_connection(DB_PATH)
    init_db(conn)
    return conn


conn = _conn()

RANK_LABELS  = {5: "🔴 CRITICAL", 4: "🟠 HIGH", 3: "🟡 MEDIUM", 2: "🔵 LOW", 1: "⚪ MINIMAL"}
RANK_COLORS  = {5: "#ef5350",    4: "#ffa726",   3: "#ffee58",   2: "#26c6da", 1: "#9e9e9e"}

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 EDGAR Monitor")
    st.markdown("---")
    view = st.radio("View", ["Alert Feed", "Watchlist", "Diff Viewer"], key="view")
    st.markdown("---")

    tickers_in_db = [
        r[0] for r in conn.execute(
            "SELECT DISTINCT ticker FROM companies ORDER BY ticker"
        ).fetchall()
    ]
    filter_ticker = st.selectbox("Filter by company", ["All"] + tickers_in_db, key="filter_ticker")
    filter_rank   = st.multiselect("Min rank", [5, 4, 3, 2, 1], default=[5, 4, 3], key="filter_rank")

    st.markdown("---")
    st.markdown("**Run Pipeline**")
    run_ticker = st.text_input("Ticker (blank = full watchlist)", placeholder="e.g. AAPL").upper().strip()
    if st.button("▶ Run Now", use_container_width=True):
        args = [sys.executable, "run_pipeline.py"]
        args += ["--ticker", run_ticker] if run_ticker else ["--all"]
        with st.spinner(f"Running pipeline for {'full watchlist' if not run_ticker else run_ticker}…"):
            result = subprocess.run(args, capture_output=True, text=True, cwd=pathlib.Path(__file__).parent)
        if result.returncode == 0:
            st.success("Pipeline complete!")
            st.cache_resource.clear()
            st.rerun()
        else:
            st.error("Pipeline error")
            st.code(result.stderr[-2000:] if result.stderr else "No stderr")

    st.markdown("---")
    st.caption("edgar-disclosure-monitor · github.com/Krish-1717")


# ── Helper ─────────────────────────────────────────────────────────────────────
def _rank_badge(rank: int) -> str:
    return f'<span style="color:{RANK_COLORS.get(rank,"#9e9e9e")};font-weight:700">{RANK_LABELS.get(rank,"—")}</span>'


# ── Alert Feed ────────────────────────────────────────────────────────────────
if view == "Alert Feed":
    st.markdown("## 📊 Alert Feed")
    st.markdown("Ranked by **Attention Gap** — high-materiality changes with low press coverage surface first.")

    ticker_arg = None if filter_ticker == "All" else filter_ticker
    alerts = get_alerts(conn, ticker=ticker_arg, limit=200)

    if not alerts:
        st.info("No alerts yet. Use the **Run Pipeline** button in the sidebar to ingest filings.")
        st.stop()

    rows = []
    for a in alerts:
        if filter_rank and a["ranking"] not in filter_rank:
            continue
        summary = json.loads(a["summary_items"] or "[]")
        top_item = summary[0]["item"] if summary else "—"
        rows.append({
            "Ticker":        a["ticker"],
            "Form":          a["form"],
            "Filed":         a["filed"],
            "Period":        a["period"],
            "Rank":          RANK_LABELS.get(a["ranking"], "—"),
            "Materiality":   round(a["materiality_score"], 1),
            "Burial":        round(a["burial_score"], 1),
            "Attention Gap": round(a["attention_gap"], 1),
            "Top Section":   f"Item {top_item}",
            "_alert_id":     a["id"],
            "_ranking":      a["ranking"],
        })

    if not rows:
        st.info("No alerts match the current filters.")
        st.stop()

    df = pd.DataFrame(rows)
    display_cols = [c for c in df.columns if not c.startswith("_")]

    # KPI row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Alerts", len(df))
    col2.metric("Critical / High", len(df[df["Rank"].str.contains("CRITICAL|HIGH")]))
    col3.metric("Avg Materiality", f"{df['Materiality'].mean():.1f}")
    col4.metric("Avg Attention Gap", f"{df['Attention Gap'].mean():.1f}")

    st.markdown("---")

    # Rank distribution bar chart
    rank_counts = df["Rank"].value_counts().reset_index()
    rank_counts.columns = ["Rank", "Count"]
    with st.expander("Rank Distribution", expanded=False):
        st.bar_chart(rank_counts.set_index("Rank"))

    st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

    # Alert detail
    st.markdown("### 🔍 Alert Detail")
    selected_idx = st.selectbox(
        "Select alert",
        range(len(rows)),
        format_func=lambda i: (
            f"{rows[i]['Ticker']}  {rows[i]['Form']}  {rows[i]['Filed']}  "
            f"{rows[i]['Rank']}  (gap {rows[i]['Attention Gap']:.1f})"
        ),
        key="selected_alert",
    )
    alert_row = rows[selected_idx]
    alert_db  = conn.execute("SELECT * FROM alerts WHERE id=?", (alert_row["_alert_id"],)).fetchone()

    if alert_db:
        summary_items = json.loads(alert_db["summary_items"] or "[]")

        st.markdown(
            f"<div class='alert-card'>"
            f"<h4>{alert_row['Ticker']} — {alert_row['Form']} filed {alert_row['Filed']}</h4>",
            unsafe_allow_html=True,
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Materiality",   f"{alert_db['materiality_score']:.1f}/100")
        c2.metric("Burial Score",  f"{alert_db['burial_score']:.1f}/100")
        c3.metric("Attention Gap", f"{alert_db['attention_gap']:.1f}")
        c4.metric("Ranking",       RANK_LABELS.get(alert_db["ranking"], "—"))

        if summary_items:
            st.markdown("**Top changed sections:**")
            for s in summary_items:
                st.markdown(f"- Item **{s['item']}** — materiality {s['score']:.1f}/100")

        st.markdown("</div>", unsafe_allow_html=True)

        if st.button("Open in Diff Viewer →", key="open_diff"):
            st.session_state["diff_new_id"] = alert_db["new_filing_id"]
            st.session_state["diff_old_id"] = alert_db["old_filing_id"]
            st.session_state["view"]         = "Diff Viewer"
            st.rerun()


# ── Watchlist ─────────────────────────────────────────────────────────────────
elif view == "Watchlist":
    st.markdown("## 🏢 Watchlist")

    companies = conn.execute("""
        SELECT c.ticker, c.name, c.sector,
               COUNT(DISTINCT f.id)           AS filings_ingested,
               MAX(f.filed)                   AS last_filed,
               COUNT(DISTINCT a.id)           AS alerts,
               ROUND(AVG(a.materiality_score),1) AS avg_materiality
        FROM companies c
        LEFT JOIN filings f ON f.ticker = c.ticker AND f.fetched = 1
        LEFT JOIN alerts  a ON a.ticker = c.ticker
        GROUP BY c.ticker
        ORDER BY c.sector, c.ticker
    """).fetchall()

    if not companies:
        st.info("No companies yet. Run the pipeline to seed the watchlist.")
        st.stop()

    df_co = pd.DataFrame([dict(r) for r in companies])
    df_co.columns = ["Ticker", "Company", "Sector",
                     "Filings Ingested", "Last Filed", "Alerts", "Avg Materiality"]
    st.dataframe(df_co, use_container_width=True, hide_index=True)

    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Filings ingested by sector**")
        sector_filings = df_co.groupby("Sector")["Filings Ingested"].sum()
        st.bar_chart(sector_filings)
    with col_b:
        st.markdown("**Alerts by sector**")
        sector_alerts = df_co.groupby("Sector")["Alerts"].sum()
        st.bar_chart(sector_alerts)


# ── Diff Viewer ───────────────────────────────────────────────────────────────
elif view == "Diff Viewer":
    st.markdown("## 🔍 Side-by-Side Diff Viewer")

    new_id = st.session_state.get("diff_new_id")
    old_id = st.session_state.get("diff_old_id")

    if not new_id or not old_id:
        st.info("Select an alert from the Alert Feed and click **Open in Diff Viewer**.")
        st.stop()

    new_filing = conn.execute("SELECT * FROM filings WHERE id=?", (new_id,)).fetchone()
    old_filing = conn.execute("SELECT * FROM filings WHERE id=?", (old_id,)).fetchone()

    if not new_filing or not old_filing:
        st.error("Filing not found in database.")
        st.stop()

    st.markdown(
        f"**{new_filing['ticker']}** &nbsp;|&nbsp; "
        f"New: `{new_filing['form']}` filed `{new_filing['filed']}` &nbsp;→&nbsp; "
        f"Prior: `{old_filing['form']}` filed `{old_filing['filed']}`"
    )

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
    selected_item = st.selectbox(
        "Section", items, key="diff_item",
        format_func=lambda x: f"Item {x}"
    )

    item_changes = [r for r in changes if r["item"] == selected_item]
    added   = [r for r in item_changes if r["change_type"] == "added"]
    removed = [r for r in item_changes if r["change_type"] == "removed"]
    revised = [r for r in item_changes if r["change_type"] == "revised"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Added",   len(added))
    c2.metric("Revised", len(revised))
    c3.metric("Removed", len(removed))

    # Legend
    st.markdown(
        '<span style="background:rgba(255,167,38,0.15);padding:2px 8px;border-radius:4px;margin-right:8px">🟠 Revised</span>'
        '<span style="background:rgba(38,198,218,0.15);padding:2px 8px;border-radius:4px;margin-right:8px">🔵 Added</span>'
        '<span style="background:rgba(239,83,80,0.12);padding:2px 8px;border-radius:4px">🔴 Removed</span>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    col_new, col_old = st.columns(2)
    col_new.markdown(f"#### New &nbsp; `{new_filing['filed']}`")
    col_old.markdown(f"#### Prior &nbsp; `{old_filing['filed']}`")

    max_show = 25
    shown = 0

    for r in revised[:max_show]:
        col_new.markdown(
            f'<div class="diff-revised">{r["new_text"][:800]}</div>',
            unsafe_allow_html=True,
        )
        col_old.markdown(
            f'<div class="diff-revised">{r["old_text"][:800]}</div>',
            unsafe_allow_html=True,
        )
        shown += 1

    for r in added[:max(0, max_show - shown)]:
        col_new.markdown(
            f'<div class="diff-added">➕ {r["new_text"][:800]}</div>',
            unsafe_allow_html=True,
        )
        col_old.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        shown += 1

    for r in removed[:max(0, max_show - shown)]:
        col_new.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        col_old.markdown(
            f'<div class="diff-removed">➖ {r["old_text"][:800]}</div>',
            unsafe_allow_html=True,
        )

    if len(item_changes) > max_show:
        st.caption(f"Showing first {max_show} of {len(item_changes)} changed paragraphs in Item {selected_item}.")
