"""Send newsletter to a single user. Edit the 3 variables below, then run:
   python send_one.py
"""
from db import init_db, get_latest_run_id, get_review_queue, log_sent_articles, log_send
from newsletter_builder import build_html
from sender import send_newsletter

init_db()

# ── Edit these ────────────────────────────────────────────────────────────────
TARGET_EMAIL = "someone@example.com"
TARGET_NAME = "Alex"
TARGET_TOPICS = ["AI", "Tech", "Crypto"]
# ──────────────────────────────────────────────────────────────────────────────

run_id = get_latest_run_id()
articles = get_review_queue(run_id=run_id, status="approved")
if not articles:
    articles = get_review_queue(run_id=run_id)[:10]

user_articles = [a for a in articles if a.get("topic") in TARGET_TOPICS][:10]
print(f"Sending {len(user_articles)} articles to {TARGET_EMAIL}...")

html = build_html(TARGET_NAME, TARGET_EMAIL, TARGET_TOPICS, user_articles)
subject = "Your TL;DR Newsletter - " + ", ".join(TARGET_TOPICS)
success = send_newsletter(TARGET_EMAIL, subject, html)

if success:
    log_send(TARGET_EMAIL, run_id)
    log_sent_articles(TARGET_EMAIL, [a["url"] for a in user_articles], run_id)
    print("Done - sent!")
else:
    print("Failed to send")
