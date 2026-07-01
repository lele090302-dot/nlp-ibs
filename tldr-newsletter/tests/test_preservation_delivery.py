"""
Preservation Property Tests — Article Delivery Minimum Spec

These tests observe and lock down existing behavior of the UNFIXED code
when the article pool is SUFFICIENT (≥8 articles score above threshold).
In the sufficient-pool case, the pipeline already behaves correctly:
- MAX_ARTICLES (10) cap is enforced
- Quality filtering excludes low-relevance articles
- Cross-edition dedup works
- Balanced topic distribution allocates slots fairly
- Feedback boost elevates preferred sources

These tests MUST PASS on unfixed code. They serve as regression guards
to ensure the cascade fix (for insufficient-pool case) doesn't break
existing behavior.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
"""

import sys
import os
import math
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

# Add parent directory to path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock heavy ML dependencies before importing nlp_pipeline
_mock_torch = MagicMock()
_mock_sentence_transformers = MagicMock()
_mock_groq = MagicMock()

sys.modules.setdefault("torch", _mock_torch)
sys.modules.setdefault("sentence_transformers", _mock_sentence_transformers)
sys.modules.setdefault("sentence_transformers.util", MagicMock())
sys.modules.setdefault("groq", _mock_groq)


# ═══════════════════════════════════════════════════════════════════════════════
# Constants matching the pipeline
# ═══════════════════════════════════════════════════════════════════════════════

VALID_TOPICS = ["AI", "Fintech", "Tech", "Startups", "Crypto"]
RELEVANCE_THRESHOLD = 0.2
MAX_ARTICLES = 10


# ═══════════════════════════════════════════════════════════════════════════════
# Strategies
# ═══════════════════════════════════════════════════════════════════════════════

@st.composite
def sufficient_pool_articles(draw, min_above_threshold=8, max_articles=20):
    """
    Generate article sets where at least `min_above_threshold` articles
    have pre-assigned scores above RELEVANCE_THRESHOLD (0.2).

    Articles are generated with pre-assigned relevance_score fields that
    will be used by the mocked score_relevance function.
    """
    num_articles = draw(st.integers(min_value=min_above_threshold, max_value=max_articles))
    topic = draw(st.sampled_from(VALID_TOPICS))

    articles = []
    above_count = 0
    for i in range(num_articles):
        # Ensure at least min_above_threshold articles score above threshold
        if above_count < min_above_threshold:
            score = draw(st.floats(min_value=0.25, max_value=0.95, allow_nan=False, allow_infinity=False))
            above_count += 1
        else:
            # Mix of above and below threshold
            score = draw(st.floats(min_value=0.05, max_value=0.95, allow_nan=False, allow_infinity=False))
            if score >= RELEVANCE_THRESHOLD:
                above_count += 1

        articles.append({
            "title": f"Article {i} about {topic}",
            "description": f"Description of article {i} covering {topic} developments",
            "topic": topic,
            "source": draw(st.sampled_from(["TechCrunch", "Bloomberg", "Reuters", "Verge", "Ars Technica"])),
            "url": f"https://example.com/article-{i}-{draw(st.integers(min_value=1000, max_value=99999))}",
            "published_at": "2025-01-01T10:00:00Z",
            "_assigned_score": round(score, 4),
        })

    return articles, [topic]


@st.composite
def abundant_pool_articles(draw):
    """
    Generate article sets where 15+ articles score above threshold.
    This tests the MAX_ARTICLES cap enforcement.
    """
    num_articles = draw(st.integers(min_value=15, max_value=25))
    topic = draw(st.sampled_from(VALID_TOPICS))

    articles = []
    for i in range(num_articles):
        # All articles score well above threshold
        score = draw(st.floats(min_value=0.3, max_value=0.95, allow_nan=False, allow_infinity=False))
        articles.append({
            "title": f"High-quality article {i}",
            "description": f"Excellent content about {topic} number {i}",
            "topic": topic,
            "source": draw(st.sampled_from(["TechCrunch", "Bloomberg", "Reuters", "Verge", "Ars Technica"])),
            "url": f"https://example.com/abundant-{i}-{draw(st.integers(min_value=1000, max_value=99999))}",
            "published_at": "2025-01-01T10:00:00Z",
            "_assigned_score": round(score, 4),
        })

    return articles, [topic]


@st.composite
def multi_topic_sufficient_pool(draw):
    """
    Generate multi-topic article sets with sufficient pool per topic.
    Each topic gets enough high-scoring articles for balanced distribution.
    """
    num_topics = draw(st.integers(min_value=2, max_value=4))
    topics = draw(st.lists(
        st.sampled_from(VALID_TOPICS),
        min_size=num_topics,
        max_size=num_topics,
        unique=True,
    ))

    # Each topic needs enough articles for balanced distribution
    articles_per_topic = draw(st.integers(min_value=4, max_value=8))

    articles = []
    for topic in topics:
        for j in range(articles_per_topic):
            score = draw(st.floats(min_value=0.3, max_value=0.9, allow_nan=False, allow_infinity=False))
            articles.append({
                "title": f"Article about {topic} #{j}",
                "description": f"Content covering {topic} developments item {j}",
                "topic": topic,
                "source": draw(st.sampled_from(["TechCrunch", "Bloomberg", "Reuters", "Verge"])),
                "url": f"https://example.com/{topic.lower()}-{j}-{draw(st.integers(min_value=1000, max_value=99999))}",
                "published_at": "2025-01-01T10:00:00Z",
                "_assigned_score": round(score, 4),
            })

    return articles, topics


@st.composite
def dedup_scenario(draw):
    """
    Generate article sets with some previously-sent URLs, ensuring the
    remaining pool (after dedup) still has ≥8 articles above threshold.
    """
    # Total articles including ones to be deduped
    num_sent = draw(st.integers(min_value=2, max_value=5))
    num_fresh = draw(st.integers(min_value=10, max_value=15))
    topic = draw(st.sampled_from(VALID_TOPICS))

    sent_urls = set()
    articles = []

    # Add articles that will be deduped
    for i in range(num_sent):
        url = f"https://example.com/sent-{i}-{draw(st.integers(min_value=1000, max_value=99999))}"
        sent_urls.add(url)
        articles.append({
            "title": f"Previously sent article {i}",
            "description": f"Old content about {topic}",
            "topic": topic,
            "source": "TechCrunch",
            "url": url,
            "published_at": "2025-01-01T10:00:00Z",
            "_assigned_score": 0.8,  # High score but should still be excluded
        })

    # Add fresh articles that should remain (all above threshold)
    for i in range(num_fresh):
        score = draw(st.floats(min_value=0.3, max_value=0.9, allow_nan=False, allow_infinity=False))
        articles.append({
            "title": f"Fresh article {i}",
            "description": f"New content about {topic} item {i}",
            "topic": topic,
            "source": draw(st.sampled_from(["TechCrunch", "Bloomberg", "Reuters", "Verge"])),
            "url": f"https://example.com/fresh-{i}-{draw(st.integers(min_value=1000, max_value=99999))}",
            "published_at": "2025-01-01T10:00:00Z",
            "_assigned_score": round(score, 4),
        })

    return articles, [topic], sent_urls


# ═══════════════════════════════════════════════════════════════════════════════
# Helper: mock score_relevance to use pre-assigned scores
# ═══════════════════════════════════════════════════════════════════════════════

def mock_score_relevance(articles, user_topics):
    """
    Return articles with relevance_score set from _assigned_score field.
    Sorted descending by score (matching real score_relevance behavior).
    """
    scored = []
    for article in articles:
        score = article.get("_assigned_score", 0.5)
        scored.append({**article, "relevance_score": score})
    return sorted(scored, key=lambda x: x["relevance_score"], reverse=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Property 2: Preservation — MAX_ARTICLES cap enforcement
#
# For all article sets where ≥8 pass threshold, result length ≤ MAX_ARTICLES (10)
#
# **Validates: Requirements 3.1**
# ═══════════════════════════════════════════════════════════════════════════════

@given(data=abundant_pool_articles())
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
def test_max_articles_cap_enforced_with_abundant_pool(data):
    """
    Property: for all article sets where ≥8 pass threshold,
    result length ≤ MAX_ARTICLES (10).

    When the pool is abundant (15+ above threshold), process_articles
    must cap output at MAX_ARTICLES regardless of how many are available.

    **Validates: Requirements 3.1**
    """
    articles, topics = data

    with patch("nlp_pipeline.score_relevance", side_effect=mock_score_relevance), \
         patch("nlp_pipeline.summarize_article", return_value="Test summary for article."), \
         patch("nlp_pipeline.rephrase_title", side_effect=lambda a: {**a, "original_title": a["title"]}), \
         patch("nlp_pipeline._fetch_full_article_text", return_value=""):

        from nlp_pipeline import process_articles
        result = process_articles(
            articles=articles,
            user_topics=topics,
            top_n=MAX_ARTICLES,
        )

    assert len(result) <= MAX_ARTICLES, (
        f"Result contains {len(result)} articles, exceeding MAX_ARTICLES ({MAX_ARTICLES}). "
        f"Input had {len(articles)} articles."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Property 2: Preservation — Quality filtering (no low-relevance articles)
#
# For all article sets where ≥8 pass threshold, no article in result
# has relevance_score < RELEVANCE_THRESHOLD
#
# **Validates: Requirements 3.2**
# ═══════════════════════════════════════════════════════════════════════════════

@given(data=sufficient_pool_articles(min_above_threshold=8, max_articles=18))
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
def test_no_below_threshold_articles_when_pool_sufficient(data):
    """
    Property: for all article sets where ≥8 pass threshold,
    no article in result has relevance_score < RELEVANCE_THRESHOLD.

    When the pool is sufficient, low-scoring articles should still be
    filtered out to maintain newsletter quality.

    **Validates: Requirements 3.2**
    """
    articles, topics = data

    with patch("nlp_pipeline.score_relevance", side_effect=mock_score_relevance), \
         patch("nlp_pipeline.summarize_article", return_value="Test summary for article."), \
         patch("nlp_pipeline.rephrase_title", side_effect=lambda a: {**a, "original_title": a["title"]}), \
         patch("nlp_pipeline._fetch_full_article_text", return_value=""):

        from nlp_pipeline import process_articles
        result = process_articles(
            articles=articles,
            user_topics=topics,
            top_n=MAX_ARTICLES,
        )

    for article in result:
        assert article["relevance_score"] >= RELEVANCE_THRESHOLD, (
            f"Article '{article['title']}' has score {article['relevance_score']} "
            f"which is below RELEVANCE_THRESHOLD ({RELEVANCE_THRESHOLD}). "
            f"When pool is sufficient, low-relevance articles should be excluded."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Property 2: Preservation — Cross-edition dedup with sufficient remaining pool
#
# For all article sets where ≥8 pass threshold AND sent_urls provided,
# no previously-sent URL appears in result
#
# **Validates: Requirements 3.3**
# ═══════════════════════════════════════════════════════════════════════════════

@given(data=dedup_scenario())
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
def test_cross_edition_dedup_excludes_sent_urls(data):
    """
    Property: for all article sets where ≥8 pass threshold AND sent_urls
    provided, no previously-sent URL appears in result.

    When remaining pool after dedup is still ≥8, cross-edition dedup
    must continue to exclude previously sent articles.

    **Validates: Requirements 3.3**
    """
    articles, topics, sent_urls = data

    with patch("nlp_pipeline.score_relevance", side_effect=mock_score_relevance), \
         patch("nlp_pipeline.summarize_article", return_value="Test summary for article."), \
         patch("nlp_pipeline.rephrase_title", side_effect=lambda a: {**a, "original_title": a["title"]}), \
         patch("nlp_pipeline._fetch_full_article_text", return_value=""):

        from nlp_pipeline import process_articles
        result = process_articles(
            articles=articles,
            user_topics=topics,
            top_n=MAX_ARTICLES,
            sent_urls=sent_urls,
        )

    result_urls = {a["url"] for a in result}
    duplicates = result_urls & sent_urls

    assert not duplicates, (
        f"Previously-sent URLs {duplicates} appear in result. "
        f"Cross-edition dedup should exclude sent_urls when pool is sufficient."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Property 2: Preservation — Balanced topic distribution
#
# For all multi-topic article sets with sufficient pool, each topic gets
# at least floor(top_n / num_topics) slots
#
# **Validates: Requirements 3.5**
# ═══════════════════════════════════════════════════════════════════════════════

@given(data=multi_topic_sufficient_pool())
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
def test_balanced_topic_distribution_allocates_fairly(data):
    """
    Property: for all multi-topic article sets with sufficient pool,
    each topic gets at least floor(top_n / num_topics) slots.

    When pool is sufficient across all topics, the balanced distribution
    should give each topic a fair share of the available slots.

    **Validates: Requirements 3.5**
    """
    articles, topics = data
    num_topics = len(topics)

    with patch("nlp_pipeline.score_relevance", side_effect=mock_score_relevance), \
         patch("nlp_pipeline.summarize_article", return_value="Test summary for article."), \
         patch("nlp_pipeline.rephrase_title", side_effect=lambda a: {**a, "original_title": a["title"]}), \
         patch("nlp_pipeline._fetch_full_article_text", return_value=""):

        from nlp_pipeline import process_articles
        result = process_articles(
            articles=articles,
            user_topics=topics,
            top_n=MAX_ARTICLES,
        )

    # Count topic distribution in result
    topic_counts = {}
    for article in result:
        t = article.get("topic", "unknown")
        topic_counts[t] = topic_counts.get(t, 0) + 1

    # Each topic should get at least floor(top_n / num_topics) slots
    # (but only if enough articles of that topic were available)
    expected_min_per_topic = MAX_ARTICLES // num_topics

    for topic in topics:
        count = topic_counts.get(topic, 0)
        # Calculate how many articles of this topic were available above threshold
        available_for_topic = sum(
            1 for a in articles
            if a.get("topic") == topic and a.get("_assigned_score", 0) >= RELEVANCE_THRESHOLD
        )
        # The minimum is capped by what's actually available for the topic
        effective_min = min(expected_min_per_topic, available_for_topic)

        assert count >= effective_min, (
            f"Topic '{topic}' got {count} slots, expected at least {effective_min} "
            f"(floor({MAX_ARTICLES}/{num_topics})={expected_min_per_topic}, "
            f"available={available_for_topic}). "
            f"Balanced distribution should allocate fairly across topics."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Property 2: Preservation — Feedback boost elevates preferred sources
#
# For all article sets where ≥8 pass threshold, applying feedback_boost
# re-ranks articles so boosted sources score higher
#
# **Validates: Requirements 3.4**
# ═══════════════════════════════════════════════════════════════════════════════

@given(data=sufficient_pool_articles(min_above_threshold=10, max_articles=15))
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
def test_feedback_boost_elevates_preferred_sources(data):
    """
    Property: for all article sets where ≥8 pass threshold, feedback_boost
    is applied additively and re-ranks articles from boosted sources.

    When pool is sufficient and feedback_boost is provided, boosted sources
    should have their scores increased (and negative boosts decrease scores).

    **Validates: Requirements 3.4**
    """
    articles, topics = data

    # Pick a source to boost
    boost_source = "TechCrunch"
    boost_value = 0.1  # Positive boost

    feedback_boost = {boost_source: boost_value}

    with patch("nlp_pipeline.score_relevance", side_effect=mock_score_relevance), \
         patch("nlp_pipeline.summarize_article", return_value="Test summary for article."), \
         patch("nlp_pipeline.rephrase_title", side_effect=lambda a: {**a, "original_title": a["title"]}), \
         patch("nlp_pipeline._fetch_full_article_text", return_value=""):

        from nlp_pipeline import process_articles

        # Run WITHOUT feedback boost
        result_no_boost = process_articles(
            articles=[{**a} for a in articles],  # Copy to avoid mutation
            user_topics=topics,
            top_n=MAX_ARTICLES,
        )

        # Run WITH feedback boost
        result_with_boost = process_articles(
            articles=[{**a} for a in articles],  # Fresh copy
            user_topics=topics,
            top_n=MAX_ARTICLES,
            feedback_boost=feedback_boost,
        )

    # Check that boosted articles in result have higher scores than without boost
    boosted_urls_in_result = [
        a for a in result_with_boost if a.get("source") == boost_source
    ]

    for boosted_article in boosted_urls_in_result:
        url = boosted_article["url"]
        # Find same article in no-boost result (if it was selected)
        no_boost_match = [a for a in result_no_boost if a["url"] == url]
        if no_boost_match:
            # When the article appears in both results, the boosted score
            # should be higher by approximately the boost value
            assert boosted_article["relevance_score"] >= no_boost_match[0]["relevance_score"], (
                f"Article from {boost_source} should have higher score with boost. "
                f"Got {boosted_article['relevance_score']} vs {no_boost_match[0]['relevance_score']}"
            )
