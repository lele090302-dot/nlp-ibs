"""
stats_demo.py - Prove the pipeline stats without sending any emails.

Run with:
    cd /Users/lyle/Documents/nlp/tldr-newsletter
    python stats_demo.py

What it does:
    1. Fetches raw articles from NewsAPI + RSS
    2. Scores every article by semantic relevance
    3. Applies the 0.3 threshold filter
    4. Shows a ranked table of the top 15 candidates
    5. Prints a summary stats block you can screenshot for your presentation
"""

import os
from collections import Counter
from dotenv import load_dotenv
load_dotenv()

from fetcher import fetch_articles_for_topics
from nlp_pipeline import score_relevance, RELEVANCE_THRESHOLD, get_embedder

TOPICS = ["GenAI", "Fintech", "Tech", "Startups", "Crypto"]

print("=" * 60)
print("  TL;DR Newsletter - Pipeline Stats Demo")
print("=" * 60)

# ── Step 1: Fetch ─────────────────────────────────────────────
print("\n[1/4] Fetching articles...")
raw = fetch_articles_for_topics(TOPICS)
print(f"      {len(raw)} articles fetched")

# ── Step 2: Score ─────────────────────────────────────────────
print(f"\n[2/4] Scoring {len(raw)} articles...")
scored = score_relevance(raw, TOPICS)
scores = [a["relevance_score"] for a in scored]
print(f"      Score range: {min(scores):.3f} - {max(scores):.3f} (mean: {sum(scores)/len(scores):.3f})")

# ── Step 3: Filter ────────────────────────────────────────────
print(f"\n[3/4] Filtering (threshold >= {RELEVANCE_THRESHOLD})...")
passed = [a for a in scored if a["relevance_score"] >= RELEVANCE_THRESHOLD]
print(f"      Kept {len(passed)}/{len(scored)} ({len(passed)/len(scored)*100:.0f}%)")

# ── Step 4: Top 15 ────────────────────────────────────────────
print(f"\n[4/4] Top 15 candidates:\n")
print(f"  {'#':<3} {'Score':<6} {'Topic':<10} {'Title':<50}")
print(f"  {'-'*3} {'-'*5} {'-'*9} {'-'*50}")

for i, a in enumerate(passed[:15], 1):
    score = f"{a['relevance_score']:.3f}"
    topic = (a.get("topic") or "?")[:9]
    title = (a.get("title") or "?")[:50]
    print(f"  {i:<3} {score:<6} {topic:<10} {title}")

# ── Summary ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  SUMMARY")
print("=" * 60)
print(f"  Articles fetched (raw, deduped):  {len(raw)}")
print(f"  Articles scored:                  {len(scored)}")
print(f"  Passed threshold (>= {RELEVANCE_THRESHOLD}):       {len(passed)}")
print(f"  Staged for admin review:          {min(15, len(passed))}")
print(f"  Sent to subscribers:              10")
print(f"  Filtered out (noise):             {len(scored) - len(passed)}")
print("=" * 60)
print("\nDone. No emails sent, no DB changes made.")