"""
scheduler.py — APScheduler-based task scheduler for EDGAR monitoring.

Schedules automated crawls, news fetching, ranking, alert dispatching,
and daily backtests. Logs all job runs to SQLite for audit and monitoring.

Usage:
    scheduler = EDGARScheduler()
    scheduler.start()
    # Runs until interrupted with Ctrl+C
"""

from __future__ import annotations

import logging
import sqlite3
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
except ImportError:
    raise ImportError("APScheduler required: pip install apscheduler")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("edgar.scheduler")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class SchedulerConfig:
    edgar_crawl_interval_min: int = 15
    news_crawl_interval_min: int  = 30
    ranker_interval_min: int      = 30
    dispatch_interval_min: int    = 5
    backtest_cron_hour: int       = 2     # 2 AM UTC daily
    backtest_cron_minute: int     = 0
    max_concurrent_jobs: int      = 4
    job_history_days: int         = 30
    data_dir: Path = field(default_factory=lambda: Path("data"))
    log_db_path: Path = field(default_factory=lambda: Path("data/scheduler_log.db"))


# ---------------------------------------------------------------------------
# Job history
# ---------------------------------------------------------------------------

class JobHistory:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS job_runs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id      TEXT NOT NULL,
                    job_name    TEXT,
                    started_at  TEXT,
                    finished_at TEXT,
                    status      TEXT,    -- 'success' | 'error' | 'skipped'
                    duration_ms INTEGER,
                    error_msg   TEXT,
                    rows_processed INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_job_id ON job_runs(job_id);
                CREATE INDEX IF NOT EXISTS idx_started ON job_runs(started_at);
            """)

    def log_start(self, job_id: str, job_name: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO job_runs (job_id, job_name, started_at, status) VALUES (?, ?, ?, ?)",
                (job_id, job_name, datetime.utcnow().isoformat(), "running"),
            )
            return cur.lastrowid

    def log_end(self, run_id: int, status: str, duration_ms: int,
                error_msg: str = "", rows: int = 0) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE job_runs SET finished_at=?, status=?, duration_ms=?,
                           error_msg=?, rows_processed=?
                   WHERE id=?""",
                (datetime.utcnow().isoformat(), status, duration_ms,
                 error_msg[:2000], rows, run_id),
            )

    def get_last_run(self, job_id: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM job_runs WHERE job_id=? ORDER BY started_at DESC LIMIT 1",
                (job_id,),
            ).fetchone()
        return dict(row) if row else None

    def recent_runs(self, limit: int = 50) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM job_runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def prune_old(self, days: int = 30) -> int:
        cutoff = datetime.utcnow().isoformat()[:10]
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                f"DELETE FROM job_runs WHERE started_at < date(?, '-{days} days')",
                (cutoff,),
            )
        return cur.rowcount


# ---------------------------------------------------------------------------
# Job implementations
# ---------------------------------------------------------------------------

def _timed_job(fn: Callable, job_id: str, job_name: str, history: JobHistory):
    """Wrapper that measures and logs each job run."""
    run_id = history.log_start(job_id, job_name)
    t0 = datetime.utcnow()
    try:
        rows = fn() or 0
        ms = int((datetime.utcnow() - t0).total_seconds() * 1000)
        history.log_end(run_id, "success", ms, rows=rows)
        logger.info(f"[{job_name}] ✓ completed in {ms}ms, {rows} rows")
    except Exception as exc:
        ms = int((datetime.utcnow() - t0).total_seconds() * 1000)
        err = traceback.format_exc()
        history.log_end(run_id, "error", ms, error_msg=err)
        logger.error(f"[{job_name}] ✗ error after {ms}ms: {exc}")


def job_crawl_edgar(config: SchedulerConfig, history: JobHistory) -> None:
    def _run():
        try:
            from edgar_web_crawler import EDGARCrawler
            crawler = EDGARCrawler(data_dir=config.data_dir)
            result = crawler.crawl_recent(max_filings=200)
            return len(result) if result else 0
        except ImportError:
            logger.warning("edgar_web_crawler not available — skipping EDGAR crawl")
            return 0
    _timed_job(_run, "crawl_edgar", "EDGAR Crawler", history)


def job_crawl_news(config: SchedulerConfig, history: JobHistory) -> None:
    def _run():
        try:
            from news_crawler import NewsCrawler
            crawler = NewsCrawler(cache_db=config.data_dir / "news_cache.db")
            articles = crawler.crawl_all(hours_back=2)
            return len(articles)
        except ImportError:
            logger.warning("news_crawler not available — skipping news crawl")
            return 0
    _timed_job(_run, "crawl_news", "News Crawler", history)


def job_run_ranker(config: SchedulerConfig, history: JobHistory) -> None:
    def _run():
        try:
            from news_relevance_ranker import NewsRelevanceRanker
            from news_crawler import NewsCrawler
            crawler = NewsCrawler(cache_db=config.data_dir / "news_cache.db")
            articles = crawler.get_cached(hours_back=1)
            ranker = NewsRelevanceRanker()
            result = ranker.rank(articles)
            logger.info(f"Ranker: {result.above_threshold}/{result.total_input} above threshold")
            return result.above_threshold
        except ImportError:
            logger.warning("news_relevance_ranker not available — skipping ranking")
            return 0
    _timed_job(_run, "run_ranker", "News Ranker", history)


def job_dispatch_alerts(config: SchedulerConfig, history: JobHistory) -> None:
    def _run():
        logger.info("Alert dispatcher: checking for pending alerts...")
        # In production: query DB for undelivered alerts, call AlertDispatcher.dispatch_batch()
        return 0
    _timed_job(_run, "dispatch_alerts", "Alert Dispatcher", history)


def job_run_backtest(config: SchedulerConfig, history: JobHistory) -> None:
    def _run():
        try:
            from news_backtest_validator import NewsBacktestValidator
            validator = NewsBacktestValidator()
            result = validator.run()
            logger.info(f"Backtest complete: pass_rate={result.pass_rate:.1%}")
            return result.total_sources
        except ImportError:
            logger.warning("news_backtest_validator not available — skipping backtest")
            return 0
    _timed_job(_run, "run_backtest", "News Backtest", history)


def job_prune_history(config: SchedulerConfig, history: JobHistory) -> None:
    removed = history.prune_old(days=config.job_history_days)
    logger.info(f"Pruned {removed} old job history rows")


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class EDGARScheduler:
    """
    Manages all scheduled jobs for the EDGAR monitor pipeline.

    Jobs:
      crawl_edgar       — every 15 min: fetch new EDGAR filings
      crawl_news        — every 30 min: fetch news articles
      run_ranker        — every 30 min: rank articles against pings
      dispatch_alerts   — every 5  min: send pending alerts
      run_backtest      — daily 02:00 UTC: validate news sources
      prune_history     — daily 03:00 UTC: remove old job logs
    """

    def __init__(
        self,
        config: Optional[SchedulerConfig] = None,
        background: bool = False,
    ):
        self.config = config or SchedulerConfig()
        self.history = JobHistory(self.config.log_db_path)
        self._sched = BackgroundScheduler() if background else BlockingScheduler()
        self._register_jobs()

    def _register_jobs(self) -> None:
        cfg = self.config

        self._sched.add_job(
            lambda: job_crawl_edgar(cfg, self.history),
            trigger=IntervalTrigger(minutes=cfg.edgar_crawl_interval_min),
            id="crawl_edgar", name="EDGAR Crawler",
            max_instances=1, replace_existing=True,
        )
        self._sched.add_job(
            lambda: job_crawl_news(cfg, self.history),
            trigger=IntervalTrigger(minutes=cfg.news_crawl_interval_min),
            id="crawl_news", name="News Crawler",
            max_instances=1, replace_existing=True,
        )
        self._sched.add_job(
            lambda: job_run_ranker(cfg, self.history),
            trigger=IntervalTrigger(minutes=cfg.ranker_interval_min),
            id="run_ranker", name="News Ranker",
            max_instances=1, replace_existing=True,
        )
        self._sched.add_job(
            lambda: job_dispatch_alerts(cfg, self.history),
            trigger=IntervalTrigger(minutes=cfg.dispatch_interval_min),
            id="dispatch_alerts", name="Alert Dispatcher",
            max_instances=1, replace_existing=True,
        )
        self._sched.add_job(
            lambda: job_run_backtest(cfg, self.history),
            trigger=CronTrigger(hour=cfg.backtest_cron_hour,
                                minute=cfg.backtest_cron_minute),
            id="run_backtest", name="News Backtest",
            max_instances=1, replace_existing=True,
        )
        self._sched.add_job(
            lambda: job_prune_history(cfg, self.history),
            trigger=CronTrigger(hour=3, minute=0),
            id="prune_history", name="History Pruner",
            max_instances=1, replace_existing=True,
        )

        self._sched.add_listener(self._on_job_event,
                                 EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    def _on_job_event(self, event) -> None:
        if hasattr(event, "exception") and event.exception:
            logger.error(f"Job {event.job_id} raised exception: {event.exception}")

    def start(self) -> None:
        logger.info("Starting EDGAR scheduler...")
        logger.info(f"  EDGAR crawl:     every {self.config.edgar_crawl_interval_min}m")
        logger.info(f"  News crawl:      every {self.config.news_crawl_interval_min}m")
        logger.info(f"  News ranker:     every {self.config.ranker_interval_min}m")
        logger.info(f"  Alert dispatch:  every {self.config.dispatch_interval_min}m")
        logger.info(f"  Daily backtest:  {self.config.backtest_cron_hour:02d}:{self.config.backtest_cron_minute:02d} UTC")
        try:
            self._sched.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")

    def stop(self) -> None:
        self._sched.shutdown(wait=False)
        logger.info("Scheduler shut down.")

    def status(self) -> list:
        return [
            {
                "job_id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time),
                "last_run": self.history.get_last_run(job.id),
            }
            for job in self._sched.get_jobs()
        ]


if __name__ == "__main__":
    import json as _json
    sched = EDGARScheduler(background=False)
    print("Starting EDGAR Disclosure Monitor Scheduler")
    print("Press Ctrl+C to stop\n")
    sched.start()
