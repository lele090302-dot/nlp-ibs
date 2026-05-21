# TL;DR Newsletter — Python Backend

The NLP pipeline and email delivery system. Fetches articles, scores relevance, generates summaries, and sends personalized newsletters via Amazon SES.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Add your API keys
python -c "from db import init_db; init_db()"
```

## Usage

```bash
# Streamlit admin UI (signup, review queue, live demo)
streamlit run app.py

# Full pipeline (fetch → rank → summarize → send)
python pipeline.py

# Phase 1 only: stage candidates for admin review
python pipeline.py --stage

# Phase 2 only: send newsletters (approved articles or AI fallback)
python pipeline.py --send

# Automated scheduler (daily 08:00 UTC, weekly Mondays)
python scheduler.py

# Stats demo (no emails sent — useful for presentations)
python stats_demo.py
```

## Module Overview

| File | Responsibility |
|------|---------------|
| `nlp_pipeline.py` | Semantic scoring, LLM summarization, reading time estimation |
| `pipeline.py` | Two-phase orchestrator (stage → send) with admin review |
| `fetcher.py` | NewsAPI + RSS fetching with deduplication |
| `newsletter_builder.py` | Jinja2 HTML rendering with feedback URLs |
| `sender.py` | Amazon SES delivery |
| `scheduler.py` | APScheduler cron jobs |
| `db.py` | SQLite operations (users, feedback, review queue) |
| `app.py` | Streamlit frontend (signup, admin panel, demo) |

## Pipeline Flow

```
fetch_articles_for_topics()     # fetcher.py
        ↓
score_relevance()               # nlp_pipeline.py — cosine similarity
        ↓
threshold filter (≥ 0.3)       # drop irrelevant articles
        ↓
feedback_boost()                # per-user source preference
        ↓
summarize_article()             # nlp_pipeline.py — Groq/Llama 3.1
        ↓
build_html()                    # newsletter_builder.py — Jinja2
        ↓
send_newsletter()               # sender.py — Amazon SES
```

## Deployment

See [EC2_SETUP.md](EC2_SETUP.md) for production deployment on AWS.
