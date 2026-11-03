"""Unit tests for watchlist_manager, data_validator, and sector_benchmarks."""
import os, json, tempfile, pytest, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from watchlist_manager import WatchlistManager
from data_validator import DataValidator
from sector_benchmarks import get_sector, rank_alert_sector_adjusted, get_sector_wacc

@pytest.fixture
def wm(tmp_path):
    path = str(tmp_path / "watchlist.json")
    return WatchlistManager(path)

def test_add_ticker(wm):
    e = wm.add("NVDA", email="k@example.com", notify_threshold="CRITICAL")
    assert e.ticker == "NVDA"
    assert e.email == "k@example.com"
    assert e.notify_threshold == "CRITICAL"
    assert e.sector == "Technology"

def test_remove_ticker(wm):
    wm.add("AAPL")
    result = wm.remove("AAPL")
    assert result is True
    assert len(wm.list_active()) == 0

def test_update_threshold(wm):
    wm.add("NKE", notify_threshold="HIGH")
    updated = wm.update("NKE", notify_threshold="CRITICAL")
    assert updated.notify_threshold == "CRITICAL"
    assert wm.get("NKE").notify_threshold == "CRITICAL"

def test_export_csv(wm, tmp_path):
    wm.add("JPM")
    wm.add("BAC")
    csv_path = str(tmp_path / "export.csv")
    wm.export_csv(csv_path)
    assert os.path.exists(csv_path)
    with open(csv_path) as f:
        content = f.read()
    assert "ticker" in content
    assert "JPM" in content

def test_validate_ticker_valid():
    v = DataValidator()
    assert v.validate_ticker("AAPL").is_valid is True

def test_validate_ticker_invalid():
    v = DataValidator()
    r = v.validate_ticker("aapl123")
    assert r.is_valid is False
    assert len(r.errors) > 0

def test_validate_materiality_out_of_range():
    v = DataValidator()
    r = v.validate_materiality_score(1.5)
    assert r.is_valid is False
    assert any("range" in e for e in r.errors)

def test_validate_filing_missing_accession():
    v = DataValidator()
    r = v.validate_filing({"form_type": "10-K", "filed_date": "2024-01-01"})
    assert r.is_valid is False
    assert any("accession" in e for e in r.errors)

def test_sector_calibration():
    assert rank_alert_sector_adjusted("NVDA", 75) == "CRITICAL"
    assert rank_alert_sector_adjusted("NKE", 70) == "CRITICAL"
    assert rank_alert_sector_adjusted("NKE", 30) == "LOW"
    assert get_sector_wacc("NVDA") > get_sector_wacc("JPM")
