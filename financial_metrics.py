"""
financial_metrics.py — Stock Return Event Study for EDGAR Disclosure Monitor

Pulls stock price data via yfinance to compute abnormal returns around filing dates.
This adds a "market reaction" signal to complement text-based scoring.

Metrics computed per filing:
  - filing_day_return    : stock return on the filing date
  - event_window_return  : cumulative return [0, +3] days
  - abnormal_return      : event return minus market return (SPY benchmark)
  - volume_ratio         : filing-day volume vs 20-day avg (unusual trading activity)
  - price_impact_score   : composite 0–100 signal (higher = more market movement)

The price_impact_score feeds into the Attention Gap calculation as an additional
signal: large text change + no market reaction = high Attention Gap (buried signal).
"""
from __future__ import annotations
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger(__name__)

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False
    log.warning("yfinance not installed. Run: pip install yfinance>=0.2.36")

try:
    import pandas as pd
    PD_AVAILABLE = True
except ImportError:
    PD_AVAILABLE = False


def _trading_days_around(date_str: str, before: int = 20, after: int = 5) -> tuple[str, str]:
    """Return (start_date, end_date) strings for the event window."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    start = (dt - timedelta(days=before + 5)).strftime("%Y-%m-%d")  # buffer for weekends
    end   = (dt + timedelta(days=after + 5)).strftime("%Y-%m-%d")
    return start, end


def get_event_returns(
    ticker: str,
    filed_date: str,
    event_window: int = 3,
    estimation_window: int = 20,
) -> dict:
    """
    Compute stock return metrics around a filing date.

    Parameters
    ----------
    ticker           : e.g. "AAPL"
    filed_date       : ISO "YYYY-MM-DD"
    event_window     : trading days after filing to measure cumulative return
    estimation_window: trading days before filing for baseline volume

    Returns
    -------
    dict with keys:
        filing_day_return, event_window_return, abnormal_return,
        volume_ratio, price_impact_score, available (bool)
    """
    null_result = {
        "filing_day_return":   None,
        "event_window_return": None,
        "abnormal_return":     None,
        "volume_ratio":        None,
        "price_impact_score":  50.0,  # neutral default
        "available":           False,
    }

    if not YF_AVAILABLE or not PD_AVAILABLE:
        return null_result

    start, end = _trading_days_around(filed_date, before=estimation_window + 5, after=event_window + 5)

    try:
        # Fetch ticker + SPY (market benchmark)
        prices = yf.download(
            [ticker, "SPY"],
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if prices.empty:
            log.warning("No price data for %s around %s", ticker, filed_date)
            return null_result

        close  = prices["Close"]
        volume = prices["Volume"]

        if ticker not in close.columns:
            return null_result

        ticker_close = close[ticker].dropna()
        spy_close    = close["SPY"].dropna() if "SPY" in close.columns else None

        # Find closest trading day at or after filing date
        filing_dt = pd.Timestamp(filed_date)
        future_idx = ticker_close.index[ticker_close.index >= filing_dt]
        if len(future_idx) == 0:
            return null_result

        event_date = future_idx[0]
        event_pos  = ticker_close.index.get_loc(event_date)

        # Filing-day return
        if event_pos == 0:
            filing_day_ret = None
        else:
            prev_close     = float(ticker_close.iloc[event_pos - 1])
            event_close    = float(ticker_close.iloc[event_pos])
            filing_day_ret = (event_close - prev_close) / prev_close if prev_close else None

        # Cumulative event window return [0, +event_window]
        window_end_pos = min(event_pos + event_window, len(ticker_close) - 1)
        if event_pos > 0:
            base          = float(ticker_close.iloc[event_pos - 1])
            window_close  = float(ticker_close.iloc[window_end_pos])
            cum_ret       = (window_close - base) / base if base else None
        else:
            cum_ret = None

        # Abnormal return: ticker return minus SPY return over same window
        abnormal = None
        if spy_close is not None and cum_ret is not None:
            spy_future = spy_close[spy_close.index >= filing_dt]
            if len(spy_future) > 0:
                spy_event_pos = spy_close.index.get_loc(spy_future.index[0])
                spy_win_pos   = min(spy_event_pos + event_window, len(spy_close) - 1)
                if spy_event_pos > 0:
                    spy_base  = float(spy_close.iloc[spy_event_pos - 1])
                    spy_win   = float(spy_close.iloc[spy_win_pos])
                    spy_ret   = (spy_win - spy_base) / spy_base if spy_base else 0.0
                    abnormal  = cum_ret - spy_ret

        # Volume ratio: filing-day volume vs 20-day pre-filing average
        vol_ratio = None
        if ticker in volume.columns:
            ticker_vol = volume[ticker].dropna()
            pre_filing = ticker_vol[ticker_vol.index < event_date]
            if len(pre_filing) >= 5:
                avg_vol = float(pre_filing.tail(estimation_window).mean())
                event_vol = float(ticker_vol.get(event_date, float("nan")))
                if avg_vol > 0 and not pd.isna(event_vol):
                    vol_ratio = event_vol / avg_vol

        # Price impact score (0–100)
        score = 50.0
        if abnormal is not None:
            # Larger absolute abnormal return = more market reaction
            abs_ab = abs(abnormal)
            score = min(abs_ab * 1000, 100.0)  # 10% abnormal = score 100
        if vol_ratio is not None:
            vol_boost = min((vol_ratio - 1.0) * 10, 30.0)  # 4× volume = +30
            score = min(score + max(vol_boost, 0), 100.0)

        return {
            "filing_day_return":   round(filing_day_ret, 5) if filing_day_ret is not None else None,
            "event_window_return": round(cum_ret, 5)        if cum_ret        is not None else None,
            "abnormal_return":     round(abnormal, 5)       if abnormal       is not None else None,
            "volume_ratio":        round(vol_ratio, 3)      if vol_ratio      is not None else None,
            "price_impact_score":  round(score, 2),
            "available":           True,
        }

    except Exception as e:
        log.warning("Price data error for %s %s: %s", ticker, filed_date, e)
        return null_result


def enrich_alerts_with_returns(
    conn: sqlite3.Connection,
    limit: int = 50,
    rate_limit_sec: float = 1.0,
) -> int:
    """
    Fetch and store event-window returns for all alerts that haven't been enriched.
    Adds columns to the `alerts` table if they don't exist yet.

    Returns number of alerts enriched.
    """
    # Ensure columns exist (migration-safe)
    for col, typ in [
        ("filing_day_return",   "REAL"),
        ("event_window_return", "REAL"),
        ("abnormal_return",     "REAL"),
        ("volume_ratio",        "REAL"),
        ("price_impact_score",  "REAL"),
    ]:
        try:
            conn.execute(f"ALTER TABLE alerts ADD COLUMN {col} {typ}")
            conn.commit()
        except Exception:
            pass  # column already exists

    alerts = conn.execute("""
        SELECT a.id, a.ticker, a.filed, f.form
        FROM alerts a
        JOIN filings f ON a.new_filing_id = f.id
        WHERE a.price_impact_score IS NULL
        ORDER BY a.id DESC
        LIMIT ?
    """, (limit,)).fetchall()

    enriched = 0
    for alert in alerts:
        metrics = get_event_returns(alert["ticker"], alert["filed"])
        conn.execute("""
            UPDATE alerts SET
                filing_day_return   = ?,
                event_window_return = ?,
                abnormal_return     = ?,
                volume_ratio        = ?,
                price_impact_score  = ?
            WHERE id = ?
        """, (
            metrics["filing_day_return"],
            metrics["event_window_return"],
            metrics["abnormal_return"],
            metrics["volume_ratio"],
            metrics["price_impact_score"],
            alert["id"],
        ))
        conn.commit()
        enriched += 1
        log.info(
            "Enriched alert %d (%s %s): abnormal_ret=%s, vol_ratio=%s",
            alert["id"], alert["ticker"], alert["filed"],
            metrics["abnormal_return"], metrics["volume_ratio"],
        )
        time.sleep(rate_limit_sec)

    return enriched


def combined_attention_gap(
    materiality: float,
    normalized_coverage: float,
    price_impact_score: float = 50.0,
    weight_coverage: float = 0.7,
    weight_price: float = 0.3,
) -> float:
    """
    Enhanced Attention Gap that blends press coverage and market reaction:

        gap = materiality / blended_signal
        blended = coverage * 0.7 + (price_impact / 100) * 0.3

    Low coverage + low market reaction → very high gap (truly hidden change).
    """
    blended = (
        weight_coverage * max(normalized_coverage, 0.01) +
        weight_price    * (price_impact_score / 100.0)
    )
    return materiality / max(blended, 0.01)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = get_event_returns("AAPL", "2024-11-01")
    print(result)
    result2 = get_event_returns("NVDA", "2024-02-21")
    print(result2)
