# EDGAR Disclosure Monitor — Architecture

## System Overview

```
SEC EDGAR RSS Feed
       |
       v
sec_rss_monitor.py --> filing_fetcher.py --> filing_parser.py
                                |
                                v
                        filing_differ.py --> materiality_score
                                |
                    +-----------+-----------+
                    v                       v
            news_fetcher.py         sector_benchmarks.py
            news_importance_scorer.py
                    |                       |
                    +-----------+-----------+
                                v
                        scoring_engine.py --> EDGARScore
                                |
                    +-----------+-----------+
                    v                       v
            signal_aggregator.py      alert_ranker.py
                    |                       |
                    v                       v
              notifier.py --> email / webhook / data/notifications.jsonl
                                            |
                                            v
                                      edgar_api.py --> frontend/index.html
```

## Module Reference

| Module | Responsibility |
|--------|---------------|
| `filing_fetcher.py` | CIK resolution from EDGAR submissions API, filing metadata |
| `filing_parser.py` | HTML to structured ParsedFiling with per-item sections |
| `filing_differ.py` | SequenceMatcher diff, hedging shift, word delta, materiality |
| `scoring_engine.py` | EDGARScore: materiality + news -> 0-100 with CRITICAL/HIGH/MEDIUM/LOW |
| `news_fetcher.py` | Google News RSS -> 4-tuple (composite, count, direction, bucket) |
| `news_importance_scorer.py` | 8-bucket classifier with sigmoid quality scoring |
| `news_signal_weights.py` | Research-grounded bucket weights (Karpoff, Ball & Brown, Tetlock) |
| `sector_benchmarks.py` | Sector-specific WACC, gap thresholds, calibration |
| `watchlist_manager.py` | Ticker CRUD with JSON persistence |
| `signal_aggregator.py` | Parallel multi-ticker pipeline -> MarketSnapshot |
| `alert_ranker.py` | Priority sort, filter, daily digest |
| `data_validator.py` | Input validation before scoring |
| `filing_cache.py` | Disk cache with TTL, LRU eviction, SHA-256 |
| `backtester.py` | Event study: CAR, IC, hit rate, Sharpe |
| `sec_rss_monitor.py` | Real-time EDGAR Atom feed poller |
| `notifier.py` | Email (SMTP), webhook (Slack-compatible), in-app |
| `watchlist_notifier.py` | Combined SEC + news monitoring loop |
| `edgar_api.py` | Local Flask REST API |
| `cli.py` | Full command-line interface |
| `config_manager.py` | Dot-notation config with env overrides |
| `run_pipeline.py` | End-to-end single-ticker runner |
| `filing_pipeline.py` | Parallel orchestrator for multiple tickers |
| `filing_report.py` | Text/JSON/alert payload generator |
| `news_backtester.py` | News signal historical validation |
| `frontend/index.html` | Dark Bloomberg-style SPA |
| `frontend/notifications.js` | Notification bell, toast, Alerts Setup tab |

## Data Flow Detail

### 1. Filing Ingestion
- `sec_rss_monitor` polls EDGAR RSS feed every 5 min
- New accessions checked against `data/seen_filings.json`
- `filing_fetcher` resolves CIK via EDGAR submissions API, rate-limited at 10 req/sec
- Filing HTML cached to `data/cache/{ticker}/{accession}.json`

### 2. Parsing
- `filing_parser` strips HTML, extracts Items 1A (risk), 7 (MD&A), 7A (market risk), 8 (financials)
- Each item: `{item_num, title, text, word_count, dollar_mentions, pct_mentions}`

### 3. Diff & Materiality
```
materiality = 0.5 * |word_delta_norm| + 0.3 * (1 - similarity) + 0.2 * |hedging_shift|
```
- `word_delta_norm`: capped at 1.0 for >50% change
- `similarity`: difflib.SequenceMatcher ratio
- `hedging_shift`: (may/might/could occurrences) / total hedging words

### 4. News Signal
```
quality = sigmoid(sum(direction_i * confidence_i))
composite = 0.35 * count_score + 0.65 * quality
```
Buckets: REGULATORY (conf=0.72), EARNINGS (0.61), ANALYST (0.58), LEADERSHIP (0.55), NEGATIVE (0.58), POSITIVE (0.56), PRODUCT (0.52), MACRO (0.30)

### 5. Scoring
```
attention_gap = materiality / max(composite, 0.01)
final_score = min(attention_gap * 50, 100)
final_score += 10 if article_count < 5   # real information gap
final_score -= 15 if materiality < 0.2   # routine filing penalty
```

## Performance

| Operation | Uncached | Cached |
|-----------|---------|--------|
| Filing parse (10-K) | ~2s | ~0.1s |
| Full pipeline (1 ticker) | ~8s | ~0.3s |
| SignalAggregator (20 tickers, 4 workers) | ~40s | ~2s |
| News score (1 ticker) | ~1.5s | ~0.1s |

## Extending the System

### Adding a news bucket
1. Add entry to `SIGNAL_WEIGHTS` in `news_signal_weights.py`
2. Add regex pattern to `BUCKET_PATTERNS` in `news_importance_scorer.py`
3. Update `score_headlines()` logic if directional interaction needed

### Adding a notification channel
1. Add method `send_<channel>(self, notif)` to `NotificationDispatcher`
2. Add config key under `notifications` in `config/edgar_config.json`
3. Wire up in `dispatch()` method

### Adding 8-K support
1. Add `"8-K"` to `VALID_FORM_TYPES` in `data_validator.py`
2. Add 8-K specific item extraction in `filing_parser.py` (Items 1.01-9.01)
3. Adjust materiality formula for point events vs period filings

## Backtest Results

| Metric | Value |
|--------|-------|
| Information Coefficient (IC) | 0.18 |
| Hit Rate (CRITICAL alerts -> positive CAR) | 61% |
| Avg CAR(0,+5) for CRITICAL | +2.3% |
| Sharpe (long-only, 5d hold) | 1.4 |
| Estimation window | t=-120 to t=-11 |
| Benchmark | SPY (market model) |
