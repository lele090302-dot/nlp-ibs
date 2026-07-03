"""
scheduler.py - Run the newsletter pipeline on a schedule.

Two-phase schedule:
  05:00 UTC (07:00 CEST) - Stage: fetch articles, rank, save queue, email admin for review
  05:50 UTC (07:50 CEST) - Send: use admin-approved articles (or AI fallback if < 10 approved)

Daily users  get emails every day.
Weekly users get emails every Monday.

Run with: python scheduler.py
"""

from apscheduler.schedulers.blocking import BlockingScheduler
from pipeline import stage_pipeline, send_pipeline
from db import init_db, get_latest_run_id

scheduler = BlockingScheduler(timezone="UTC")


# ── Daily users ───────────────────────────────────────────────────────────────

@scheduler.scheduled_job("cron", hour=5, minute=0)
def daily_stage():
    """Stage articles for daily subscribers at 05:00 UTC (07:00 CEST)."""
    print("[Scheduler] Daily stage job starting...")
    stage_pipeline(frequency_filter="daily")


@scheduler.scheduled_job("cron", hour=5, minute=50)
def daily_send():
    """Send to daily subscribers at 05:50 UTC (07:50 CEST) - 50 min review window."""
    print("[Scheduler] Daily send job starting...")
    run_id = get_latest_run_id()
    send_pipeline(run_id=run_id, frequency_filter="daily")


# ── Weekly users (Mondays only) ───────────────────────────────────────────────

@scheduler.scheduled_job("cron", day_of_week="mon", hour=5, minute=0)
def weekly_stage():
    """Stage articles for weekly subscribers every Monday at 05:00 UTC (07:00 CEST)."""
    print("[Scheduler] Weekly stage job starting...")
    stage_pipeline(frequency_filter="weekly")


@scheduler.scheduled_job("cron", day_of_week="mon", hour=5, minute=50)
def weekly_send():
    """Send to weekly subscribers every Monday at 05:50 UTC (07:50 CEST)."""
    print("[Scheduler] Weekly send job starting...")
    run_id = get_latest_run_id()
    send_pipeline(run_id=run_id, frequency_filter="weekly")


if __name__ == "__main__":
    init_db()
    print("[Scheduler] Starting... Press Ctrl+C to stop.")
    print("[Scheduler] Schedule:")
    print("  05:00 UTC (07:00 CEST) daily   - stage (fetch + rank + notify admin)")
    print("  05:50 UTC (07:50 CEST) daily   - send  (approved or AI fallback)")
    print("  05:00 UTC (07:00 CEST) Monday  - stage (weekly users)")
    print("  05:50 UTC (07:50 CEST) Monday  - send  (weekly users)")
    scheduler.start()
