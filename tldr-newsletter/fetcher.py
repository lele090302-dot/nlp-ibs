import os
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateutil_parser
from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# RSS feeds per topic as fallback / supplement
RSS_FEEDS = {
    "GenAI": [
        "https://feeds.feedburner.com/venturebeat/SZYF",  # VentureBeat AI
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://arstechnica.com/ai/",
        "https://www.bloomberg.com/ai",
    ],
    "Fintech": [
        "https://www.finextra.com/rss/headlines.aspx",
        "https://techcrunch.com/category/fintech/feed/",
        "https://fintechmagazine.com/fintech",
    ],
    "Tech": [
        "https://feeds.feedburner.com/TechCrunch",
        "https://www.theverge.com/rss/index.xml",
        "https://arstechnica.com/gadgets/",
        "https://www.bloomberg.com/technology",
        "https://www.wsj.com/tech/ai",
    ],
    "Startups": [
        "https://techcrunch.com/category/startups/feed/",
        "https://www.bloomberg.com/technology/startups",
    ],
    "Crypto": [
        "https://cointelegraph.com/rss",
        "https://decrypt.co/feed",
        "https://fintechmagazine.com/crypto",
    ],
}

# NewsAPI keyword mapping per topic
TOPIC_KEYWORDS = {
    "GenAI": "generative AI OR large language model OR ChatGPT OR LLM",
    "Fintech": "fintech OR neobank OR digital payments OR open banking",
    "Tech": "technology OR software OR silicon valley OR big tech",
    "Startups": "startup OR venture capital OR seed funding OR Series A",
    "Crypto": "bitcoin OR ethereum OR cryptocurrency OR blockchain OR DeFi",
}


def fetch_from_newsapi(topic: str, page_size: int = 20, freshness_days: int = 3) -> list[dict]:
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
        "sortBy": "publishedAt",
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


def fetch_from_rss(topic: str, max_per_feed: int = 10, freshness_days: int = 3) -> list[dict]:
    """Fetch articles from RSS feeds for a given topic."""
    articles = []
    feeds = RSS_FEEDS.get(topic, [])
    cutoff = datetime.now(timezone.utc) - timedelta(days=freshness_days)

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_per_feed]:
                pub_date_str = entry.get("published", "")
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
        except Exception as e:
            print(f"[RSS] Error fetching {feed_url}: {e}")

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


def fetch_articles_for_topics(topics: list[str], freshness_days: int = 3) -> list[dict]:
    """Main entry point: fetch and deduplicate articles for a list of topics."""
    all_articles = []

    for topic in topics:
        newsapi_articles = fetch_from_newsapi(topic, freshness_days=freshness_days)
        rss_articles = fetch_from_rss(topic, freshness_days=freshness_days)
        all_articles.extend(newsapi_articles)
        all_articles.extend(rss_articles)

    return deduplicate(all_articles)
