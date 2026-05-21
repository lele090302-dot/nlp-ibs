# ⚡ TL;DR Newsletter — AI-Powered News Digest Platform

> A full-stack NLP system that fetches, ranks, summarizes, and delivers personalized newsletters to subscribers. Built to solve a real problem: staying informed during a 15-minute commute.

## The Problem

As a university student commuting 15 minutes by train each morning, I wanted a way to stay on top of tech, AI, and fintech news without doomscrolling or reading 20-minute articles. Existing newsletters were either too long, too generic, or not personalized to my interests.

## The Solution

TL;DR Newsletter is an end-to-end NLP pipeline that:
1. **Fetches** 100+ articles daily from NewsAPI and curated RSS feeds
2. **Ranks** them using semantic similarity (not keyword matching) against each subscriber's chosen topics
3. **Summarizes** the top 10 into 2-3 sentence TL;DRs using an LLM
4. **Delivers** a beautifully formatted, personalized email every morning before 8am

The result: a 5-minute read that covers exactly what matters to you.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION                                │
│  NewsAPI (keyword queries)  +  RSS Feeds (TechCrunch, Verge, etc.) │
│                              ↓                                       │
│                     Deduplication (URL + fuzzy title)                │
└──────────────────────────────┬──────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         NLP PIPELINE                                  │
│                                                                      │
│  1. Semantic Relevance Scoring                                       │
│     └─ sentence-transformers (all-MiniLM-L6-v2)                     │
│     └─ Cosine similarity: article embedding ↔ topic embedding       │
│     └─ Threshold filter (≥ 0.3) to remove noise                     │
│                                                                      │
│  2. Feedback-Based Personalization                                   │
│     └─ Per-user source boosting from thumbs up/down history         │
│     └─ Score adjustment: ±0.05 per signal, capped at ±0.15         │
│                                                                      │
│  3. LLM Summarization                                                │
│     └─ Groq API (Llama 3.1 8B Instant)                             │
│     └─ Prompt-engineered for concise, factual 2-3 sentence TL;DRs  │
│                                                                      │
│  4. Reading Time Estimation                                          │
│     └─ Word count / 200 WPM                                         │
└──────────────────────────────┬──────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      EDITORIAL REVIEW                                 │
│                                                                      │
│  Two-phase pipeline:                                                 │
│    Phase 1 (07:00 UTC): Stage top 15 candidates → admin review      │
│    Phase 2 (08:00 UTC): Send approved picks + AI padding to 10      │
│                                                                      │
│  Admin gets an email with approve/reject buttons per article.        │
│  If no editorial input, AI's top 10 go out automatically.           │
└──────────────────────────────┬──────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        DELIVERY                                       │
│                                                                      │
│  Jinja2 HTML template → Amazon SES                                   │
│  Personalized per subscriber (name, topics, feedback links)          │
│  Daily (every morning) or Weekly (Mondays) cadence                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
nlp/
├── tldr-newsletter/          # Python backend — NLP pipeline & email delivery
│   ├── nlp_pipeline.py       # Core NLP: embeddings, scoring, summarization
│   ├── pipeline.py           # Orchestrator: stage → review → send
│   ├── fetcher.py            # Multi-source article fetching (NewsAPI + RSS)
│   ├── newsletter_builder.py # Jinja2 HTML rendering with feedback URLs
│   ├── sender.py             # Amazon SES email delivery
│   ├── scheduler.py          # APScheduler cron jobs (daily/weekly)
│   ├── db.py                 # SQLite: users, feedback, review queue
│   ├── app.py                # Streamlit UI: signup, admin panel, live demo
│   ├── templates/            # Email HTML template
│   └── deploy_ec2.sh         # EC2 deployment script
│
├── tldr-landing/             # Next.js landing page — subscriber frontend
│   ├── app/                  # App router pages & API routes
│   │   ├── api/subscribe/    # Writes to shared SQLite DB
│   │   └── api/stocks/       # Live SPY market data (Twelve Data API)
│   └── components/           # React components (Hero, Features, Stories, etc.)
│
└── README.md                 # ← You are here
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| NLP - Embeddings | `sentence-transformers` (all-MiniLM-L6-v2) | Semantic relevance scoring via cosine similarity |
| NLP - Summarization | Groq API (Llama 3.1 8B) | Fast, concise article summaries |
| Data Ingestion | NewsAPI + RSS (feedparser) | Multi-source article fetching |
| Backend | Python, Streamlit | Pipeline orchestration, admin UI |
| Frontend | Next.js 14, React 18, Tailwind CSS | Landing page, subscriber signup |
| Database | SQLite (shared between frontend & backend) | Users, preferences, feedback, review queue |
| Email | Amazon SES + Jinja2 | Personalized HTML newsletter delivery |
| Scheduling | APScheduler | Cron-based daily/weekly pipeline runs |
| Market Data | Twelve Data API | Live S&P 500 stock ticker on landing page |
| Deployment | AWS EC2 + systemd | Production scheduler service |

---

## NLP Techniques Demonstrated

### 1. Semantic Similarity Scoring
Rather than keyword matching, articles are scored by computing cosine similarity between their title+description embedding and the user's topic description embedding. This captures meaning — an article about "Meta's new open-source LLM" correctly matches a "GenAI" topic even without the exact keyword.

### 2. Embedding-Based Filtering
A relevance threshold (0.3) filters out noise. From 100+ fetched articles, typically 40-60% pass the threshold, ensuring only genuinely relevant content reaches subscribers.

### 3. LLM-Powered Summarization
Each article is summarized into 2-3 factual sentences using a prompt-engineered template. The prompt explicitly avoids filler phrases ("This article discusses...") and focuses on the key insight.

### 4. Feedback Loop / Reinforcement
Subscribers can thumbs-up or thumbs-down individual stories. This feedback adjusts future relevance scores per source — if you consistently like TechCrunch articles, they'll rank slightly higher in your next newsletter.

### 5. Deduplication
URL-based and fuzzy title-based deduplication prevents the same story from appearing twice when it's covered by multiple sources.

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- API keys (see below)

### Backend Setup

```bash
cd tldr-newsletter
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Fill in your API keys
python -c "from db import init_db; init_db()"  # Initialize database
```

### Frontend Setup

```bash
cd tldr-landing
npm install
# Create .env.local with TWELVE_DATA_API_KEY (optional, for live stock data)
npm run dev
```

### Run the Pipeline

```bash
# Start the Streamlit admin UI
streamlit run app.py

# Run the full pipeline manually (fetch → rank → summarize → send)
python pipeline.py

# Or run phases separately:
python pipeline.py --stage   # Fetch + rank + save to review queue
python pipeline.py --send    # Send newsletters (uses approved articles or AI fallback)

# Start the automated scheduler
python scheduler.py
```

---

## Environment Variables

| Variable | Service | Description |
|----------|---------|-------------|
| `NEWS_API_KEY` | [newsapi.org](https://newsapi.org) | Article fetching (free tier: 100 req/day) |
| `GROQ_API_KEY` | [groq.com](https://groq.com) | LLM summarization (free tier available) |
| `AWS_ACCESS_KEY_ID` | AWS | SES email sending |
| `AWS_SECRET_ACCESS_KEY` | AWS | SES email sending |
| `AWS_REGION` | AWS | SES region (e.g. `us-east-1`) |
| `SES_SENDER_EMAIL` | AWS SES | Verified sender address |
| `ADMIN_EMAIL` | — | Receives review queue notifications |
| `TWELVE_DATA_API_KEY` | [twelvedata.com](https://twelvedata.com) | Live stock prices (landing page) |

---

## Deployment

The scheduler runs as a systemd service on AWS EC2. See [`tldr-newsletter/EC2_SETUP.md`](tldr-newsletter/EC2_SETUP.md) for the full deployment guide, including:
- IAM role configuration (no stored credentials on instance)
- User-data bootstrap script
- systemd service unit
- Auto-update via cron

---

## Screenshots

*Landing page and newsletter email screenshots can be added here.*

---

## What I Learned

- Sentence embeddings are surprisingly effective for content relevance scoring — much better than TF-IDF or keyword matching for this use case
- Prompt engineering matters: small changes to the summarization prompt dramatically affect output quality
- A two-phase pipeline (stage → review → send) gives editorial control without blocking automation
- Feedback loops create a virtuous cycle — even simple thumbs up/down signals meaningfully improve personalization over time
- Sharing a SQLite database between a Python backend and Next.js frontend is pragmatic for a solo project but wouldn't scale to production

---

## Future Improvements

- [ ] Named Entity Recognition (NER) for auto-tagging people, companies, and products
- [ ] Sentiment analysis to flag controversial or negative stories
- [ ] Clustering to group related stories and avoid redundancy
- [ ] PostgreSQL for multi-user production deployment
- [ ] A/B testing different summarization prompts
- [ ] Click-through tracking for better relevance feedback

---

## License

This project was built as a university coursework project. Feel free to explore the code.
