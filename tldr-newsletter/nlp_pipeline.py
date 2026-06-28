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


def _balanced_select(ranked: list[dict], user_topics: list[str], top_n: int) -> list[dict]:
    """
    Select top_n articles with balanced representation across user_topics.

    Strategy:
    1. Allocate slots equally: each topic gets floor(top_n / num_topics) slots.
    2. Remaining slots (from rounding) are distributed round-robin to topics
       that still have available articles, ordered by highest next-article score.
    3. Fill each topic's allocation with its highest-scored articles.
    4. If a topic can't fill its slots (not enough articles), redistribute
       those empty slots to other topics that have surplus candidates.
    """
    num_topics = len(user_topics)
    if num_topics == 0:
        return ranked[:top_n]

    # Group articles by topic (preserving score order within each group)
    by_topic: dict[str, list[dict]] = {t: [] for t in user_topics}
    uncategorized: list[dict] = []

    for article in ranked:
        topic = article.get("topic", "")
        if topic in by_topic:
            by_topic[topic].append(article)
        else:
            uncategorized.append(article)

    # Base allocation per topic
    base_per_topic = top_n // num_topics
    remainder = top_n - (base_per_topic * num_topics)

    # Determine how many slots each topic gets
    allocation: dict[str, int] = {t: base_per_topic for t in user_topics}

    # Distribute remainder slots to topics that have the most available articles
    topics_by_availability = sorted(
        user_topics,
        key=lambda t: len(by_topic[t]),
        reverse=True,
    )
    for i in range(remainder):
        allocation[topics_by_availability[i % num_topics]] += 1

    # Fill each topic's allocation
    selected: list[dict] = []
    unfilled_slots = 0

    for topic in user_topics:
        available = by_topic[topic]
        take = min(allocation[topic], len(available))
        selected.extend(available[:take])
        unfilled_slots += allocation[topic] - take

    # Redistribute unfilled slots: pick from topics with leftover articles or uncategorized
    if unfilled_slots > 0:
        already_selected_urls = {a.get("url") for a in selected}
        # Candidates: remaining articles from any topic + uncategorized, by score
        overflow_candidates = []
        for topic in user_topics:
            taken_count = min(allocation[topic], len(by_topic[topic]))
            overflow_candidates.extend(by_topic[topic][taken_count:])
        overflow_candidates.extend(uncategorized)
        overflow_candidates = [
            a for a in overflow_candidates if a.get("url") not in already_selected_urls
        ]
        overflow_candidates.sort(key=lambda x: x["relevance_score"], reverse=True)
        selected.extend(overflow_candidates[:unfilled_slots])

    # Final sort by relevance so the newsletter reads well (highest first)
    selected.sort(key=lambda x: x["relevance_score"], reverse=True)

    topic_counts = {}
    for a in selected:
        t = a.get("topic", "unknown")
        topic_counts[t] = topic_counts.get(t, 0) + 1
    print(f"[NLP] Balanced distribution: {topic_counts} (total {len(selected)})")

    return selected[:top_n]


def process_articles(
    articles: list[dict],
    user_topics: list[str],
    top_n: int = 10,
    min_articles: int = 8,
    feedback_boost: dict[str, float] | None = None,
) -> list[dict]:
    """
    Full NLP pipeline:
    1. Score relevance for user topics
    2. Apply relevance threshold — drop articles below RELEVANCE_THRESHOLD
    3. Apply feedback boost — articles from sources the user liked rank higher
    4. Pick top N articles (minimum min_articles, maximum top_n)
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

    # If we still don't have enough articles after filtering, lower threshold further
    if len(ranked) < min_articles:
        print(f"[NLP] Warning: only {len(ranked)} articles after filtering, need at least {min_articles}. Lowering threshold to 0.05.")
        ranked = score_relevance(articles, user_topics)
        ranked = [a for a in ranked if a["relevance_score"] >= 0.05]

    # Apply feedback boost: bump score for sources the user has liked before
    if feedback_boost:
        for article in ranked:
            boost = feedback_boost.get(article.get("source", ""), 0.0)
            article["relevance_score"] = round(article["relevance_score"] + boost, 4)
        # Re-sort after boost adjustments
        ranked = sorted(ranked, key=lambda x: x["relevance_score"], reverse=True)
        print(f"[NLP] Feedback boost applied for {len(feedback_boost)} source(s).")

    # ── Balanced topic distribution ───────────────────────────────────────────
    # Instead of taking the global top_n (which can skew heavily toward one topic),
    # distribute slots equally across the user's topics, then fill any remaining
    # slots from the overall ranked list.
    top_articles = _balanced_select(ranked, user_topics, top_n)

    # Ensure we have at least min_articles
    if len(top_articles) < min_articles:
        print(f"[NLP] Warning: only {len(top_articles)} articles selected, minimum is {min_articles}.")

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
