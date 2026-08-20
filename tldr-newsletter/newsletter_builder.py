import os
from urllib.parse import urlencode
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Base URL for email links (feedback, unsubscribe, preferences).
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://codesonline.rocks")


def build_feedback_url(base_url: str, email: str, article_url: str, article_source: str, article_topic: str, signal: int) -> str:
    """Build a feedback URL that encodes all context needed to log the vote."""
    params = urlencode({
        "email": email,
        "url": article_url,
        "source": article_source,
        "topic": article_topic,
        "signal": signal,
    })
    return f"{base_url}/api/feedback?{params}"


def build_html(user_name: str, user_email: str, topics: list[str], articles: list[dict], max_bytes: int = 95000) -> str:
    """Render the newsletter HTML from the Jinja2 template."""
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("newsletter.html")

    # Attach feedback URLs to each article before rendering
    for article in articles:
        article["feedback_up_url"] = build_feedback_url(
            APP_BASE_URL, user_email,
            article.get("url", ""), article.get("source", ""), article.get("topic", ""),
            signal=1,
        )
        article["feedback_down_url"] = build_feedback_url(
            APP_BASE_URL, user_email,
            article.get("url", ""), article.get("source", ""), article.get("topic", ""),
            signal=-1,
        )

    # Build unsubscribe URL
    unsubscribe_url = f"{APP_BASE_URL}/api/unsubscribe?{urlencode({'email': user_email})}"

    html = template.render(
        user_name=user_name,
        topics=topics,
        articles=articles,
        date=datetime.utcnow().strftime("%B %d, %Y"),
        unsubscribe_url=unsubscribe_url,
    )

    # Size guard: reduce articles if HTML exceeds Gmail clip limit
    while len(html.encode('utf-8')) > max_bytes and len(articles) > 5:
        articles = articles[:-1]  # Drop lowest-ranked (last) article
        html = template.render(
            user_name=user_name,
            topics=topics,
            articles=articles,
            date=datetime.utcnow().strftime("%B %d, %Y"),
            unsubscribe_url=unsubscribe_url,
        )

    return html
