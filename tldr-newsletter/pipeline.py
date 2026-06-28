"""
pipeline.py - Main orchestrator.

Two-phase flow:
  Phase 1 (stage_pipeline):  Fetch articles, rank top 15, save to review queue,
                              email admin a review digest.
  Phase 2 (send_pipeline):   Use admin-approved articles (if >= 10 approved),
                              otherwise fall back to AI top 8-10 automatically.

Run both phases manually:
  python pipeline.py --stage   # fetch + queue + notify admin
  python pipeline.py --send    # send newsletters to subscribers
  python pipeline.py           # run both phases back-to-back (demo / manual)
"""

import os
import uuid
from datetime import datetime, timezone

from db import (
    init_db,
    get_all_active_users,
    get_feedback_boost,
    save_review_queue,
    get_approved_articles,
    get_latest_run_id,
    get_review_queue,
    clear_old_queues,
)
from fetcher import fetch_articles_for_topics
from nlp_pipeline import process_articles, score_relevance, summarize_article, estimate_reading_time, RELEVANCE_THRESHOLD
from newsletter_builder import build_html
from sender import send_to_all_users, send_newsletter


ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8501")

# How many candidates to surface for admin review
REVIEW_POOL_SIZE = 15

# Minimum approved articles needed to use admin picks; below this, fall back to AI
MIN_APPROVED_FOR_OVERRIDE = 1  # any approval triggers editorial mode

# Article count constraints for the final newsletter
MIN_ARTICLES = 8
MAX_ARTICLES = 10


# ── Phase 1: Stage ────────────────────────────────────────────────────────────

def stage_pipeline(frequency_filter: str | None = None) -> str | None:
    """
    Fetch articles, rank top REVIEW_POOL_SIZE, save to review queue,
    send admin a review email. Returns the run_id.
    """
    print("=" * 50)
    print("[Pipeline] Phase 1: Staging review queue...")
    print("=" * 50)

    users = get_all_active_users(frequency_filter=frequency_filter)
    if not users:
        print("[Pipeline] No active subscribers. Skipping stage.")
        return None

    # Collect all unique topics
    all_topics: set[str] = set()
    for user in users:
        for topic in user["topics"].split(","):
            all_topics.add(topic.strip())

    print(f"[Pipeline] Topics: {all_topics}")
    raw_articles = fetch_articles_for_topics(list(all_topics))
    print(f"[Pipeline] Fetched {len(raw_articles)} raw articles.")

    # Score and filter globally (not per-user) for the admin queue
    from sentence_transformers import SentenceTransformer, util as st_util
    from nlp_pipeline import get_embedder, TOPIC_DESCRIPTIONS

    embedder = get_embedder()
    combined_topic_text = " | ".join(TOPIC_DESCRIPTIONS.get(t, t) for t in all_topics)
    topic_embedding = embedder.encode(combined_topic_text, convert_to_tensor=True)

    scored = []
    for article in raw_articles:
        text = f"{article['title']}. {article.get('description', '')}"
        article_embedding = embedder.encode(text, convert_to_tensor=True)
        score = float(st_util.cos_sim(topic_embedding, article_embedding))
        scored.append({**article, "relevance_score": round(score, 4)})

    scored = [a for a in scored if a["relevance_score"] >= RELEVANCE_THRESHOLD]
    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    candidates = scored[:REVIEW_POOL_SIZE]

    # Summarize candidates
    print(f"[Pipeline] Summarizing {len(candidates)} candidates for review...")
    for i, article in enumerate(candidates):
        print(f"  [{i+1}/{len(candidates)}] {article['title'][:60]}...")
        article["summary"] = summarize_article(article)
        article["reading_time"] = estimate_reading_time(
            article.get("content") or article.get("description") or ""
        )

    # Save to DB
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    save_review_queue(run_id, candidates)
    clear_old_queues(keep_latest=5)
    print(f"[Pipeline] Saved {len(candidates)} articles to review queue. run_id={run_id}")

    # Email admin
    if ADMIN_EMAIL:
        _send_admin_review_email(run_id, candidates)
    else:
        print("[Pipeline] ADMIN_EMAIL not set - skipping admin notification. Review via Streamlit admin tab.")

    return run_id


def _send_admin_review_email(run_id: str, articles: list[dict]):
    """Send the admin a digest email with approve/reject links for each article."""
    rows_html = ""
    for i, a in enumerate(articles, 1):
        approve_url = f"{APP_BASE_URL}/?admin_action=approve&run_id={run_id}&url={a['url']}"
        reject_url  = f"{APP_BASE_URL}/?admin_action=reject&run_id={run_id}&url={a['url']}"
        score_pct   = int(a.get("relevance_score", 0) * 100)

        rows_html += f"""
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:14px 8px;font-size:13px;color:#888;font-weight:bold;">{i}</td>
          <td style="padding:14px 8px;">
            <div style="font-weight:600;font-size:14px;color:#1E1B18;margin-bottom:4px;">
              <a href="{a['url']}" style="color:#C83A2A;text-decoration:none;">{a['title']}</a>
            </div>
            <div style="font-size:12px;color:#888;margin-bottom:6px;">
              {a.get('source','?')} &middot; {a.get('topic','?')} &middot; {a.get('reading_time',1)} min &middot; Score: {score_pct}%
            </div>
            <div style="font-size:13px;color:#4b5563;line-height:1.5;">{a.get('summary','')}</div>
          </td>
          <td style="padding:14px 8px;white-space:nowrap;vertical-align:top;">
            <a href="{approve_url}"
               style="display:inline-block;background:#C83A2A;color:white;padding:6px 14px;
                      border-radius:20px;font-size:12px;font-weight:600;text-decoration:none;margin-bottom:6px;">
              Approve
            </a><br>
            <a href="{reject_url}"
               style="display:inline-block;background:#f3f4f6;color:#6b7280;padding:6px 14px;
                      border-radius:20px;font-size:12px;font-weight:600;text-decoration:none;">
              Reject
            </a>
          </td>
        </tr>"""

    html = f"""
    <!DOCTYPE html><html><body style="font-family:-apple-system,sans-serif;background:#FFF8F3;margin:0;padding:0;">
    <div style="max-width:700px;margin:32px auto;background:#fff;border-radius:12px;
                overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
      <div style="background:#C83A2A;padding:28px 32px;">
        <h1 style="color:#fff;margin:0;font-size:20px;">TL;DR Admin Review</h1>
        <p style="color:rgba(255,255,255,0.75);margin:6px 0 0;font-size:13px;">
          {len(articles)} candidates for run <code style="color:#fff;">{run_id}</code> -
          approve any stories to include them. Approved picks come first; AI fills
          remaining slots to always deliver {MIN_ARTICLES}-{MAX_ARTICLES} stories.
          If you approve nothing, the AI top {MAX_ARTICLES} go out automatically.
        </p>
      </div>
      <div style="padding:24px 32px;">
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr style="border-bottom:2px solid #F8ECE8;">
              <th style="padding:8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;">#</th>
              <th style="padding:8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;">Article</th>
              <th style="padding:8px;text-align:left;font-size:11px;color:#9ca3af;text-transform:uppercase;">Action</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>
      <div style="background:#F8ECE8;padding:16px 32px;text-align:center;">
        <p style="font-size:12px;color:#9ca3af;margin:0;">
          Or review and edit in the
          <a href="{APP_BASE_URL}" style="color:#C83A2A;">Streamlit admin panel</a>.
        </p>
      </div>
    </div>
    </body></html>"""

    success = send_newsletter(
        ADMIN_EMAIL,
        f"[TL;DR Admin] Review {len(articles)} articles - run {run_id}",
        html,
    )
    if success:
        print(f"[Pipeline] Admin review email sent to {ADMIN_EMAIL}.")
    else:
        print(f"[Pipeline] Failed to send admin review email.")


# ── Phase 2: Send ─────────────────────────────────────────────────────────────

def send_pipeline(run_id: str | None = None, frequency_filter: str | None = None):
    """
    Build and send newsletters to all active subscribers.
    Uses admin-approved articles if >= MIN_APPROVED_FOR_OVERRIDE are approved,
    otherwise falls back to AI top 8-10 per user.
    """
    print("=" * 50)
    print("[Pipeline] Phase 2: Sending newsletters...")
    print("=" * 50)

    users = get_all_active_users(frequency_filter=frequency_filter)
    if not users:
        print("[Pipeline] No active subscribers. Exiting.")
        return

    # Determine article source: admin-approved or AI fallback
    approved: list[dict] = []
    if run_id:
        approved = get_approved_articles(run_id)
        print(f"[Pipeline] Admin approved {len(approved)} articles for run {run_id}.")

    use_admin_picks = len(approved) >= MIN_APPROVED_FOR_OVERRIDE

    if use_admin_picks:
        print(f"[Pipeline] Using {len(approved)} admin-approved articles.")
    else:
        print(f"[Pipeline] Fewer than {MIN_APPROVED_FOR_OVERRIDE} approved - falling back to AI selection (targeting {MIN_ARTICLES}-{MAX_ARTICLES} articles).")

    # Fetch raw articles for AI fallback (only if needed)
    raw_articles: list[dict] = []
    if not use_admin_picks:
        all_topics: set[str] = set()
        for user in users:
            for topic in user["topics"].split(","):
                all_topics.add(topic.strip())
        raw_articles = fetch_articles_for_topics(list(all_topics))
        print(f"[Pipeline] Fetched {len(raw_articles)} raw articles for AI fallback.")

    html_by_email: dict[str, str] = {}
    for user in users:
        user_topics = [t.strip() for t in user["topics"].split(",")]
        feedback_boost = get_feedback_boost(user["email"])

        if use_admin_picks:
            # Start with approved articles filtered to this user's topics
            user_approved = [a for a in approved if a.get("topic") in user_topics]
            # If fewer than MAX_ARTICLES approved for this user's topics, add remaining approved articles
            if len(user_approved) < MAX_ARTICLES:
                extras = [a for a in approved if a not in user_approved]
                user_approved += extras[:MAX_ARTICLES - len(user_approved)]

            # Still short of MIN_ARTICLES? Pad with AI-ranked articles not already included
            if len(user_approved) < MIN_ARTICLES:
                approved_urls = {a["url"] for a in user_approved}
                # Fetch and rank remaining articles as fallback padding
                if not raw_articles:
                    all_topics_fallback: set[str] = set()
                    for u in users:
                        for t in u["topics"].split(","):
                            all_topics_fallback.add(t.strip())
                    raw_articles = fetch_articles_for_topics(list(all_topics_fallback))

                user_raw = [a for a in raw_articles
                            if a.get("topic") in user_topics
                            and a.get("url") not in approved_urls]
                ai_padding = process_articles(
                    user_raw,
                    user_topics,
                    top_n=MAX_ARTICLES - len(user_approved),
                    feedback_boost=feedback_boost,
                )
                user_approved += ai_padding
                print(f"[Pipeline] Padded with {len(ai_padding)} AI picks to reach {MIN_ARTICLES}-{MAX_ARTICLES}.")

            enriched = user_approved[:MAX_ARTICLES]
        else:
            user_articles = [a for a in raw_articles if a.get("topic") in user_topics]
            enriched = process_articles(
                user_articles,
                user_topics,
                top_n=MAX_ARTICLES,
                feedback_boost=feedback_boost,
            )

        print(f"[Pipeline] Building newsletter for {user['email']} ({len(enriched)} articles)")
        html = build_html(
            user_name=user["name"],
            user_email=user["email"],
            topics=user_topics,
            articles=enriched,
        )
        html_by_email[user["email"]] = html

    print("\n[Pipeline] Sending emails via Amazon SES...")
    send_to_all_users(users, html_by_email)
    print("\n[Pipeline] Done.")


# ── Combined run (manual / demo) ──────────────────────────────────────────────

def run_pipeline(frequency_filter: str | None = None):
    """Run both phases back-to-back. Used for manual runs and the Streamlit demo button."""
    run_id = stage_pipeline(frequency_filter=frequency_filter)
    send_pipeline(run_id=run_id, frequency_filter=frequency_filter)


if __name__ == "__main__":
    import sys
    init_db()

    if "--stage" in sys.argv:
        stage_pipeline()
    elif "--send" in sys.argv:
        run_id = get_latest_run_id()
        send_pipeline(run_id=run_id)
    else:
        run_pipeline()
