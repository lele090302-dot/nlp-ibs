import os
import math
from groq import Groq
from sentence_transformers import SentenceTransformer, util
from dotenv import load_dotenv

load_dotenv()


def get_groq_client():
    """Lazy-init Groq client so missing key doesn't crash at import time."""
    return Groq(api_key=os.getenv("GROQ_API_KEY"))

# Loaded once at module level to avoid reloading on every call
_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        print("[NLP] Loading sentence-transformer model...")
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


# ── 1. Relevance Scoring ──────────────────────────────────────────────────────

TOPIC_DESCRIPTIONS = {
    "GenAI": "generative artificial intelligence, large language models, GPT, AI tools, machine learning breakthroughs",
    "Fintech": "financial technology, digital banking, payments, neobanks, open banking, insurtech",
    "Tech": "technology industry, software, hardware, big tech companies, product launches",
    "Startups": "startup ecosystem, venture capital, funding rounds, entrepreneurship, new companies",
    "Crypto": "cryptocurrency, bitcoin, ethereum, blockchain, decentralized finance, NFTs, web3",
}


def score_relevance(articles: list[dict], user_topics: list[str]) -> list[dict]:
    """
    Score each article by cosine similarity between its title+description
    and the user's chosen topic descriptions.
    Returns articles sorted by relevance score descending.
    """
    embedder = get_embedder()

    # Build a combined topic description for this user
    combined_topic_text = " | ".join(
        TOPIC_DESCRIPTIONS.get(t, t) for t in user_topics
    )
    topic_embedding = embedder.encode(combined_topic_text, convert_to_tensor=True)

    scored = []
    for article in articles:
        text = f"{article['title']}. {article['description']}"
        article_embedding = embedder.encode(text, convert_to_tensor=True)
        score = float(util.cos_sim(topic_embedding, article_embedding))
        scored.append({**article, "relevance_score": round(score, 4)})

    return sorted(scored, key=lambda x: x["relevance_score"], reverse=True)


# ── 2. Summarization ──────────────────────────────────────────────────────────

SUMMARIZE_PROMPT = """You are a concise newsletter writer for busy professionals.
Summarize the following article in exactly 2-3 sentences. 
Be factual, clear, and highlight the key insight or news.
Do not start with "This article" or "The article".

Article title: {title}
Article content: {content}

TL;DR:"""


def summarize_article(article: dict) -> str:
    """Generate a 2-3 sentence TL;DR summary using OpenAI."""
    content = article.get("content") or article.get("description") or article["title"]
    # Truncate to avoid token limits
    content = content[:2000]

    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "user",
                    "content": SUMMARIZE_PROMPT.format(
                        title=article["title"], content=content
                    ),
                }
            ],
            max_tokens=120,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[NLP] Summarization error for '{article['title']}': {e}")
        # Fallback: return truncated description
        return (article.get("description") or article["title"])[:200]


# ── 3. Reading Time Estimation ────────────────────────────────────────────────

AVG_WORDS_PER_MINUTE = 200


def estimate_reading_time(text: str) -> int:
    """Estimate reading time in minutes. Minimum 1 minute."""
    word_count = len(text.split())
    minutes = math.ceil(word_count / AVG_WORDS_PER_MINUTE)
    return max(1, minutes)


# ── 4. Full Pipeline ──────────────────────────────────────────────────────────

# Minimum cosine similarity score for an article to be included in the newsletter.
# Articles below this threshold are considered too loosely related to the user's topics.
RELEVANCE_THRESHOLD = 0.3


def process_articles(
    articles: list[dict],
    user_topics: list[str],
    top_n: int = 10,
    feedback_boost: dict[str, float] | None = None,
) -> list[dict]:
    """
    Full NLP pipeline:
    1. Score relevance for user topics
    2. Apply relevance threshold — drop articles below RELEVANCE_THRESHOLD
    3. Apply feedback boost — articles from sources the user liked rank higher
    4. Pick top N articles
    5. Summarize each
    6. Estimate reading time
    Returns enriched article dicts ready for the newsletter.

    feedback_boost: optional dict mapping article source name → boost value (e.g. {"TechCrunch": 0.05})
    """
    print(f"[NLP] Scoring {len(articles)} articles for relevance...")
    ranked = score_relevance(articles, user_topics)

    # Filter out articles below the relevance threshold
    before_filter = len(ranked)
    ranked = [a for a in ranked if a["relevance_score"] >= RELEVANCE_THRESHOLD]
    print(f"[NLP] Threshold filter ({RELEVANCE_THRESHOLD}): {before_filter} → {len(ranked)} articles kept.")

    if not ranked:
        print("[NLP] Warning: no articles passed the relevance threshold. Lowering threshold to 0.1 as fallback.")
        ranked = score_relevance(articles, user_topics)
        ranked = [a for a in ranked if a["relevance_score"] >= 0.1]

    # Apply feedback boost: bump score for sources the user has liked before
    if feedback_boost:
        for article in ranked:
            boost = feedback_boost.get(article.get("source", ""), 0.0)
            article["relevance_score"] = round(article["relevance_score"] + boost, 4)
        # Re-sort after boost adjustments
        ranked = sorted(ranked, key=lambda x: x["relevance_score"], reverse=True)
        print(f"[NLP] Feedback boost applied for {len(feedback_boost)} source(s).")

    top_articles = ranked[:top_n]

    print(f"[NLP] Summarizing top {len(top_articles)} articles...")
    enriched = []
    for i, article in enumerate(top_articles):
        print(f"  [{i+1}/{len(top_articles)}] {article['title'][:60]}...")
        summary = summarize_article(article)
        reading_time = estimate_reading_time(
            article.get("content") or article.get("description") or ""
        )
        enriched.append({
            **article,
            "summary": summary,
            "reading_time": reading_time,
        })

    return enriched
