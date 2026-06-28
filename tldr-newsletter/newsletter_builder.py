import os
from urllib.parse import urlencode
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

# Base URL where the Streamlit app is running — used to build feedback links in emails.
# Override via APP_BASE_URL env var in production.
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8501")


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


def build_html(user_name: str, user_email: str, topics: list[str], articles: list[dict]) -> str:
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

    # Build unsubscribe and preferences URLs
    unsubscribe_url = f"{APP_BASE_URL}/api/unsubscribe?{urlencode({'email': user_email})}"
    preferences_url = f"{APP_BASE_URL}/#hero-form"

    return template.render(
        user_name=user_name,
        topics=topics,
        articles=articles,
        date=datetime.utcnow().strftime("%B %d, %Y"),
        unsubscribe_url=unsubscribe_url,
        preferences_url=preferences_url,
        logo_url=f"{APP_BASE_URL}/logo.png",
    )
