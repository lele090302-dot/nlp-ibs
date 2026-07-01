"""
Bug Condition Exploration Test — Article Delivery Minimum Guarantee

Property 1: Bug Condition — Minimum Article Delivery Guarantee

GOAL: Surface counterexamples that demonstrate the pipeline delivers fewer than
MIN_ARTICLES (8) for niche-topic subscribers when fewer than 8 articles pass
the RELEVANCE_THRESHOLD (0.2).

On UNFIXED code, this test is EXPECTED TO FAIL — failure confirms the bug exists:
the system delivers <8 articles with no corrective cascade.

After implementing the progressive threshold cascade fix, this test should PASS.

Validates: Requirements 2.2, 2.3, 2.4, 2.6
"""

import sys
import os
import logging
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, assume, note
from hypothesis import strategies as st

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock out heavy ML dependencies before importing project modules
_mock_st = MagicMock()
_mock_st.SentenceTransformer = MagicMock
_mock_st.util = MagicMock()
_mock_st.util.cos_sim = MagicMock(return_value=0.8)

sys.modules["sentence_transformers"] = _mock_st
sys.modules["sentence_transformers.util"] = _mock_st.util

# Mock groq client
_mock_groq = MagicMock()
sys.modules["groq"] = _mock_groq

# Now we can import project modules safely
from nlp_pipeline import process_articles, RELEVANCE_THRESHOLD


# ─── Strategies ───────────────────────────────────────────────────────────────

MIN_ARTICLES_EXPECTED = 8


def relevance_score_strategy():
    """
    Generate a list of relevance scores where fewer than MIN_ARTICLES_EXPECTED (8)
    are above RELEVANCE_THRESHOLD (0.2), simulating niche-topic scenarios.

    Strategy: generate 10-20 articles total, but only 4-7 score above 0.2.
    The rest score between 0.01 and 0.19 (below threshold).
    """
    # Number of articles that score ABOVE threshold (fewer than 8)
    num_above = st.integers(min_value=2, max_value=7)
    # Number of articles that score BELOW threshold
    num_below = st.integers(min_value=4, max_value=12)

    return st.tuples(num_above, num_below)


def article_strategy(num_articles: int, topic: str):
    """Generate a list of article dicts for testing."""
    articles = []
    for i in range(num_articles):
        articles.append({
            "title": f"Article {i}: Niche Topic Coverage on {topic}",
            "url": f"https://example.com/articles/{topic.lower()}/{i:04d}",
            "source": f"Source_{i % 3}",
            "published_at": "2024-12-01T10:00:00+00:00",
            "description": f"Description for article {i} about {topic} developments.",
            "content": f"Full content about {topic} news and insights for article {i}. " * 5,
            "topic": topic,
        })
    return articles


# ─── Test Class ───────────────────────────────────────────────────────────────


class TestMinimumArticleDeliveryGuarantee:
    """
    Property 1: Bug Condition — Minimum Article Delivery Guarantee

    For any pipeline execution where the initial filtering produces fewer than
    MIN_ARTICLES (8) articles for a subscriber, the fixed system SHALL activate
    the progressive constraint-relaxation cascade and deliver at least MIN_ARTICLES
    articles, OR exhaust all fallback strategies and log an explicit alert while
    delivering all available articles.

    On UNFIXED code: process_articles just prints a warning and delivers the
    insufficient count. No cascade exists. Test FAILS, proving the bug.

    Validates: Requirements 2.2, 2.3, 2.4, 2.6
    """

    @given(
        num_above_threshold=st.integers(min_value=2, max_value=7),
        num_below_threshold=st.integers(min_value=4, max_value=12),
        topic=st.sampled_from(["Fintech", "Startups", "Crypto"]),
    )
    @settings(max_examples=30, deadline=None)
    def test_pipeline_delivers_minimum_or_alerts_when_few_pass_threshold(
        self, num_above_threshold, num_below_threshold, topic
    ):
        """
        **Validates: Requirements 2.2, 2.3, 2.4, 2.6**

        Generate article sets where fewer than 8 articles score above
        RELEVANCE_THRESHOLD (0.2). The system should activate a progressive
        cascade to deliver at least 8, or log an alert if impossible.

        On UNFIXED code: process_articles delivers only the articles above
        threshold (2-7), prints a warning, and takes no corrective action.
        This test FAILS, confirming the bug.
        """
        total_articles = num_above_threshold + num_below_threshold

        # Ensure we have enough total articles that meeting minimum IS possible
        # (there are ≥8 articles total, just not enough above threshold)
        assume(total_articles >= MIN_ARTICLES_EXPECTED)

        # Ensure fewer than 8 pass the threshold (the bug condition)
        assume(num_above_threshold < MIN_ARTICLES_EXPECTED)

        # Build article list
        all_articles = article_strategy(total_articles, topic)

        # Pre-assign relevance scores: some above 0.2, rest below
        scored_articles = []
        for i, article in enumerate(all_articles):
            if i < num_above_threshold:
                # Above threshold: score between 0.21 and 0.6
                score = 0.21 + (i * 0.05)
            else:
                # Below threshold: score between 0.05 and 0.19
                score = 0.05 + ((i - num_above_threshold) * 0.01)
                score = min(score, 0.19)
            scored_articles.append({**article, "relevance_score": round(score, 4)})

        # Sort by score descending (as score_relevance does)
        scored_articles.sort(key=lambda x: x["relevance_score"], reverse=True)

        note(f"Total articles: {total_articles}")
        note(f"Articles above threshold (0.2): {num_above_threshold}")
        note(f"Articles below threshold: {num_below_threshold}")
        note(f"Topic: {topic}")

        # Mock score_relevance to return our pre-scored articles
        def mock_score_relevance(articles_in, user_topics):
            """Return articles with pre-assigned scores."""
            return scored_articles[:len(articles_in)]

        # Mock summarize_article to avoid LLM calls
        def mock_summarize(article):
            return "This is a test summary for the article."

        # Capture log output to check for alerts
        alert_logged = False
        original_warning = logging.warning

        def capture_alert(*args, **kwargs):
            nonlocal alert_logged
            alert_logged = True
            original_warning(*args, **kwargs)

        with patch("nlp_pipeline.score_relevance", side_effect=mock_score_relevance), \
             patch("nlp_pipeline.summarize_article", side_effect=mock_summarize), \
             patch("nlp_pipeline.rephrase_title", side_effect=lambda a: {**a, "original_title": a["title"]}), \
             patch("nlp_pipeline._fetch_full_article_text", return_value=""), \
             patch("logging.warning", side_effect=capture_alert):

            result = process_articles(
                articles=all_articles,
                user_topics=[topic],
                top_n=10,
                min_articles=MIN_ARTICLES_EXPECTED,
            )

        result_count = len(result)

        note(f"Result count: {result_count}")
        note(f"Alert logged: {alert_logged}")

        # ── ASSERTIONS ────────────────────────────────────────────────────────
        # The system MUST deliver at least MIN_ARTICLES_EXPECTED (8) articles,
        # OR if that's impossible, exhaust all fallback strategies and log an alert.
        #
        # On UNFIXED code: delivers only num_above_threshold (2-7) with no cascade.
        # This assertion FAILS, proving the bug exists.

        all_fallbacks_exhausted_and_alert = (
            result_count < MIN_ARTICLES_EXPECTED
            and alert_logged
            and result_count == total_articles  # delivered everything available
        )

        assert result_count >= MIN_ARTICLES_EXPECTED or all_fallbacks_exhausted_and_alert, (
            f"BUG CONFIRMED: Pipeline delivered only {result_count} articles "
            f"(minimum is {MIN_ARTICLES_EXPECTED}). "
            f"Only {num_above_threshold} of {total_articles} articles scored above "
            f"RELEVANCE_THRESHOLD ({RELEVANCE_THRESHOLD}). "
            f"No progressive cascade was triggered to meet the minimum. "
            f"Alert logged: {alert_logged}. "
            f"The system just printed a warning and delivered insufficient articles."
        )

    @given(
        num_above_threshold=st.integers(min_value=2, max_value=6),
        num_below_threshold=st.integers(min_value=5, max_value=10),
        topic=st.sampled_from(["Fintech", "Startups", "Crypto"]),
    )
    @settings(max_examples=20, deadline=None)
    def test_all_returned_articles_have_valid_title_and_url(
        self, num_above_threshold, num_below_threshold, topic
    ):
        """
        **Validates: Requirements 2.2, 2.6**

        Assert that all articles returned by process_articles have non-empty
        title and non-empty url fields. This validates data integrity regardless
        of how many articles are returned.
        """
        total_articles = num_above_threshold + num_below_threshold
        assume(total_articles >= MIN_ARTICLES_EXPECTED)
        assume(num_above_threshold < MIN_ARTICLES_EXPECTED)

        all_articles = article_strategy(total_articles, topic)

        scored_articles = []
        for i, article in enumerate(all_articles):
            if i < num_above_threshold:
                score = 0.25 + (i * 0.04)
            else:
                score = 0.05 + ((i - num_above_threshold) * 0.012)
                score = min(score, 0.19)
            scored_articles.append({**article, "relevance_score": round(score, 4)})

        scored_articles.sort(key=lambda x: x["relevance_score"], reverse=True)

        def mock_score_relevance(articles_in, user_topics):
            return scored_articles[:len(articles_in)]

        def mock_summarize(article):
            return "Test summary."

        with patch("nlp_pipeline.score_relevance", side_effect=mock_score_relevance), \
             patch("nlp_pipeline.summarize_article", side_effect=mock_summarize), \
             patch("nlp_pipeline.rephrase_title", side_effect=lambda a: {**a, "original_title": a["title"]}), \
             patch("nlp_pipeline._fetch_full_article_text", return_value=""):

            result = process_articles(
                articles=all_articles,
                user_topics=[topic],
                top_n=10,
                min_articles=MIN_ARTICLES_EXPECTED,
            )

        # All returned articles must have non-empty title and url
        for article in result:
            assert article.get("title") and article["title"].strip(), (
                f"Article missing or empty title: {article}"
            )
            assert article.get("url") and article["url"].strip(), (
                f"Article missing or empty url: {article}"
            )
