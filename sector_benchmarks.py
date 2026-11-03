"""Sector-aware signal calibration for EDGAR Disclosure Monitor."""
from dataclasses import dataclass

SECTOR_PROFILES = {
    "Technology": {"wacc": 0.095, "gap_critical": 70, "gap_high": 50, "avg_materiality": 0.42},
    "Consumer Discretionary": {"wacc": 0.085, "gap_critical": 65, "gap_high": 45, "avg_materiality": 0.35},
    "Financials": {"wacc": 0.080, "gap_critical": 60, "gap_high": 40, "avg_materiality": 0.38},
    "Healthcare": {"wacc": 0.090, "gap_critical": 68, "gap_high": 48, "avg_materiality": 0.40},
    "Energy": {"wacc": 0.088, "gap_critical": 55, "gap_high": 35, "avg_materiality": 0.45},
    "Industrials": {"wacc": 0.082, "gap_critical": 58, "gap_high": 38, "avg_materiality": 0.36},
    "Communication Services": {"wacc": 0.092, "gap_critical": 67, "gap_high": 47, "avg_materiality": 0.39},
    "Default": {"wacc": 0.086, "gap_critical": 63, "gap_high": 43, "avg_materiality": 0.38},
}

TICKER_SECTOR = {
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology", "GOOGL": "Communication Services",
    "META": "Communication Services", "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary",
    "JPM": "Financials", "BAC": "Financials", "GS": "Financials", "WFC": "Financials",
    "JNJ": "Healthcare", "LLY": "Healthcare", "PFE": "Healthcare", "ABBV": "Healthcare",
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy",
    "NKE": "Consumer Discretionary", "NFLX": "Communication Services",
    "INTC": "Technology", "AMD": "Technology",
    "CAT": "Industrials", "GE": "Industrials", "HON": "Industrials",
}

def get_sector(ticker: str) -> str:
    return TICKER_SECTOR.get(ticker.upper(), "Default")

def get_sector_profile(ticker: str) -> dict:
    return SECTOR_PROFILES[get_sector(ticker)]

def calibrate_gap(ticker: str, raw_gap: float) -> float:
    """Normalize gap relative to sector baseline."""
    profile = get_sector_profile(ticker)
    return raw_gap / max(profile["avg_materiality"], 0.01) * 0.38

def rank_alert_sector_adjusted(ticker: str, raw_gap: float) -> str:
    profile = get_sector_profile(ticker)
    if raw_gap >= profile["gap_critical"]: return "CRITICAL"
    if raw_gap >= profile["gap_high"]: return "HIGH"
    if raw_gap >= profile["gap_high"] * 0.67: return "MEDIUM"
    return "LOW"

def get_sector_wacc(ticker: str) -> float:
    return get_sector_profile(ticker)["wacc"]

if __name__ == "__main__":
    for t in ["NVDA", "NKE", "JPM", "XOM"]:
        print(f"{t} ({get_sector(t)}): WACC={get_sector_wacc(t):.1%}, gap_critical={get_sector_profile(t)['gap_critical']}")
        print(f"  Gap=70 -> {rank_alert_sector_adjusted(t, 70)}")
