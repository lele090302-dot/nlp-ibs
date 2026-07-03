import os
import json
import logging
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateutil_parser
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# RSS feeds per topic as fallback / supplement
RSS_FEEDS = {
    "AI": [
        "https://feeds.feedburner.com/venturebeat/SZYF",  # VentureBeat AI
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://arstechnica.com/ai/feed/",
    ],
    "Fintech": [
        "https://www.finextra.com/rss/headlines.aspx",
        "https://techcrunch.com/category/fintech/feed/",
    ],
    "Tech": [
        "https://feeds.feedburner.com/TechCrunch",
        "https://www.theverge.com/rss/index.xml",
        "https://arstechnica.com/gadgets/feed/",
    ],
    "Startups": [
        "https://techcrunch.com/category/startups/feed/",
    ],
    "Crypto": [
        "https://cointelegraph.com/rss",
        "https://decrypt.co/feed",
    ],
}

# NewsAPI keyword mapping per topic
# Strategy: (actors OR category terms) AND (event signals) for high-precision results.
# NOTE: NewsAPI 'q' param has a 500-char max. Keep each query well under that.
# Update actor lists monthly as the landscape shifts.
TOPIC_KEYWORDS = {
    "AI": (
        "(OpenAI OR Anthropic OR Nvidia OR \"Scale AI\" OR Google DeepMind OR Mistral OR xAI"
        " OR Meta AI OR ChatGPT OR Claude OR Gemini OR LLM OR \"AI agents\""
        " OR \"reasoning model\" OR \"AI infrastructure\" OR \"data center\""
        " OR robotics OR \"artificial intelligence\")"
        " AND (launch OR announce OR release OR funding OR regulation"
        " OR partnership OR acquisition OR benchmark OR safety OR open-source)"
    ),
    "Fintech": (
        "(Stripe OR Revolut OR Plaid OR Square OR Nubank OR Klarna OR Wise"
        " OR Adyen OR Robinhood OR fintech OR neobank OR \"open banking\""
        " OR \"embedded finance\" OR \"digital payments\")"
        " AND (launch OR funding OR IPO OR partnership OR regulation"
        " OR acquisition OR expansion OR earnings OR breach)"
    ),
    "Tech": (
        "(Apple OR Google OR Microsoft OR Amazon OR Meta OR Nvidia OR Samsung"
        " OR TSMC OR Intel OR Qualcomm OR semiconductor OR cybersecurity"
        " OR \"quantum computing\" OR \"cloud computing\" OR robotics)"
        " AND (launch OR announce OR release OR earnings OR acquisition"
        " OR antitrust OR layoff OR partnership OR hack OR outage)"
        " NOT (recipe OR movie OR \"TV show\" OR sports)"
    ),
    "Startups": (
        "(\"venture capital\" OR \"startup funding\" OR \"seed round\" OR \"Series A\""
        " OR \"Series B\" OR unicorn OR YC OR \"Y Combinator\" OR Techstars"
        " OR a16z OR Sequoia OR Accel OR startup OR founder)"
        " AND (raised OR funding OR valuation OR IPO OR acquisition"
        " OR launch OR pivot OR layoff OR accelerator OR \"demo day\")"
    ),
    "Crypto": (
        "(Bitcoin OR Ethereum OR Solana OR Coinbase OR Binance OR Ripple"
        " OR Tether OR Circle OR cryptocurrency OR DeFi OR stablecoin"
        " OR tokenization OR \"crypto ETF\" OR \"crypto regulation\""
        " OR SEC OR blockchain)"
        " AND (price OR ruling OR launch OR hack OR ETF OR regulation"
        " OR partnership OR upgrade OR adoption OR ban)"
    ),
}


def fetch_from_newsapi(topic: str, page_size: int = 20, freshness_days: int = 5) -> list[dict]:
    """Fetch articles from NewsAPI for a given topic."""
    if not NEWS_API_KEY:
        return []

    query = TOPIC_KEYWORDS.get(topic, topic)
    from_date = (datetime.now(timezone.utc) - timedelta(days=freshness_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "from": from_date,
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": page_size,
        "apiKey": NEWS_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        return [
            {
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "source": a.get("source", {}).get("name", "Unknown"),
                "published_at": a.get("publishedAt", ""),
                "description": a.get("description", "") or "",
                "content": a.get("content", "") or "",
                "topic": topic,
            }
            for a in articles
            if a.get("title") and a.get("url")
        ]
    except Exception as e:
        print(f"[NewsAPI] Error fetching {topic}: {e}")
        return []


def fetch_from_rss(topic: str, max_per_feed: int = 10, freshness_days: int = 5) -> list[dict]:
    """Fetch articles from RSS feeds for a given topic."""
    articles = []
    feeds = RSS_FEEDS.get(topic, [])
    cutoff = datetime.now(timezone.utc) - timedelta(days=freshness_days)

    for feed_url in feeds:
        try:
            response = requests.get(feed_url, timeout=10)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            # Bozo flag checking
            if feed.bozo:
                if len(feed.entries) == 0:
                    logger.warning(
                        f"[RSS] Malformed feed with no entries, skipping: {feed_url} "
                        f"(bozo_exception: {feed.bozo_exception})"
                    )
                    continue
                else:
                    logger.warning(
                        f"[RSS] Malformed feed but has entries, continuing: {feed_url} "
                        f"(bozo_exception: {feed.bozo_exception})"
                    )

            for entry in feed.entries[:max_per_feed]:
                # Entry title/URL validation
                if not entry.get("title") or not entry.get("link"):
                    continue

                # Date field fallback for Atom feeds
                pub_date_str = entry.get("published") or entry.get("updated", "")
                if pub_date_str:
                    try:
                        pub_date = dateutil_parser.parse(pub_date_str)
                        if pub_date.tzinfo is None:
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                        if pub_date < cutoff:
                            continue  # Skip stale articles
                    except (ValueError, TypeError):
                        pass  # If unparseable, include it (benefit of the doubt)

                articles.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "source": feed.feed.get("title", "RSS"),
                    "published_at": pub_date_str,
                    "description": entry.get("summary", "") or "",
                    "content": entry.get("summary", "") or "",
                    "topic": topic,
                })
        except requests.exceptions.Timeout:
            logger.warning(f"[RSS] Timeout fetching {feed_url} (10s limit exceeded)")
        except requests.exceptions.RequestException as e:
            logger.warning(f"[RSS] Error fetching {feed_url}: {e}")
        except Exception as e:
            logger.warning(f"[RSS] Unexpected error processing {feed_url}: {e}")

    return articles


def deduplicate(articles: list[dict]) -> list[dict]:
    """Remove duplicate articles by URL and near-duplicate titles."""
    seen_urls = set()
    seen_titles = set()
    unique = []

    for article in articles:
        url = article["url"]
        # Normalize title for fuzzy dedup (lowercase, strip punctuation)
        title_key = "".join(c for c in article["title"].lower() if c.isalnum())[:60]

        if url in seen_urls or title_key in seen_titles:
            continue

        seen_urls.add(url)
        seen_titles.add(title_key)
        unique.append(article)

    return unique


MANUAL_ARTICLES_PATH = os.path.join(os.path.dirname(__file__), "manual_articles.json")


def fetch_manual_articles() -> list[dict]:
    """Load manually curated articles from the local JSON file."""
    if not os.path.exists(MANUAL_ARTICLES_PATH):
        return []
    try:
        with open(MANUAL_ARTICLES_PATH, "r") as f:
            articles = json.load(f)
        # Add published_at if missing so recency scoring doesn't penalize them
        for a in articles:
            if not a.get("published_at"):
                a["published_at"] = datetime.now(timezone.utc).isoformat()
        return [a for a in articles if a.get("title") and a.get("url")]
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"[Manual] Error reading manual articles: {e}")
        return []


def fetch_articles_for_topics(topics: list[str], freshness_days: int = 5) -> list[dict]:
    """Main entry point: fetch and deduplicate articles for a list of topics."""
    all_articles = []

    for topic in topics:
        newsapi_articles = fetch_from_newsapi(topic, freshness_days=freshness_days)
        rss_articles = fetch_from_rss(topic, freshness_days=freshness_days)
        all_articles.extend(newsapi_articles)
        all_articles.extend(rss_articles)

    # Include manually curated articles
    manual = fetch_manual_articles()
    if manual:
        logger.info(f"[Manual] Adding {len(manual)} manually curated article(s)")
    all_articles.extend(manual)

    return deduplicate(all_articles)
