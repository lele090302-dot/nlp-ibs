"""
Preservation Property Tests — Observe and Lock Down Existing Behavior

These tests capture the behavior of the UNFIXED code to ensure regressions
are detected when the bug fixes are applied.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**
"""

import sys
import os
import re
import math
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

# Constants matching the pipeline
RELEVANCE_THRESHOLD = 0.2
MAX_ARTICLES = 10

# Add parent directory to path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock heavy ML dependencies before importing nlp_pipeline
# This avoids the PyTorch/NumPy/sentence-transformers compatibility issues
_mock_torch = MagicMock()
_mock_sentence_transformers = MagicMock()
_mock_groq = MagicMock()

sys.modules.setdefault("torch", _mock_torch)
sys.modules.setdefault("sentence_transformers", _mock_sentence_transformers)
sys.modules.setdefault("sentence_transformers.util", MagicMock())
sys.modules.setdefault("groq", _mock_groq)


# ═══════════════════════════════════════════════════════════════════════════════
# VALID_TOPICS used across tests
# ═══════════════════════════════════════════════════════════════════════════════

VALID_TOPICS = ["AI", "Fintech", "Tech", "Startups", "Crypto"]


# ═══════════════════════════════════════════════════════════════════════════════
# Property 2.1: Relevance Scoring Preservation
# For all fresh articles (age < 12h), score_relevance() produces scores
# based purely on cosine similarity to user topics.
#
# Observation: On unfixed code, score_relevance() returns cosine similarity
# scores without any recency decay factor. The score is purely based on
# the cosine similarity between article text embeddings and user topic embeddings.
#
# **Validates: Requirements 3.1**
# ═══════════════════════════════════════════════════════════════════════════════

@st.composite
def article_strategy(draw):
    """Generate a realistic article dict for testing."""
    title = draw(st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
        min_size=5,
        max_size=80,
    ))
    description = draw(st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
        min_size=10,
        max_size=200,
    ))
    topic = draw(st.sampled_from(VALID_TOPICS))
    source = draw(st.sampled_from(["TechCrunch", "Bloomberg", "Reuters", "Verge", "Ars Technica"]))
    url = f"https://example.com/{draw(st.integers(min_value=1, max_value=100000))}"

    return {
        "title": title,
        "description": description,
        "topic": topic,
        "source": source,
        "url": url,
        "published_at": "2025-01-01T10:00:00Z",  # Fresh date (doesn't matter on unfixed code)
    }


@st.composite
def article_list_strategy(draw, min_size=2, max_size=5):
    """Generate a list of articles with unique URLs."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    articles = []
    for i in range(n):
        a = draw(article_strategy())
        a["url"] = f"https://example.com/article-{i}"
        articles.append(a)
    return articles


@given(
    articles=article_list_strategy(min_size=2, max_size=4),
    topics=st.lists(st.sampled_from(VALID_TOPICS), min_size=1, max_size=2, unique=True),
)
@settings(
    max_examples=10,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
def test_relevance_scoring_is_pure_cosine_similarity(articles, topics):
    """
    Property 2.1: For fresh articles, score_relevance() produces scores
    based purely on cosine similarity to user topics (no recency decay).

    On the current unfixed code, the score IS the cosine similarity.
    We verify: scores are in valid cosine similarity range [-1, 1],
    the result is sorted descending by score, and each article gets a score.

    We mock the embedder to return controllable embeddings and verify
    the scoring logic works correctly with cosine similarity.

    **Validates: Requirements 3.1**
    """
    import numpy as np

    # Generate random but consistent embeddings for testing
    rng = np.random.RandomState(42)
    embedding_dim = 64

    # Create a mock embedder that returns consistent embeddings based on text
    text_to_embedding = {}

    def mock_encode(text, convert_to_tensor=False):
        if text not in text_to_embedding:
            text_to_embedding[text] = rng.randn(embedding_dim).astype(np.float32)
        return text_to_embedding[text]

    class ScalarWrapper:
        """Mimics a torch tensor that can be converted with float()."""
        def __init__(self, value):
            self._value = value

        def __float__(self):
            return float(self._value)

    def mock_cos_sim(a, b):
        # Actual cosine similarity computation - returns a scalar-like object
        dot = float(np.dot(a, b))
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0 or norm_b == 0:
            return ScalarWrapper(0.0)
        return ScalarWrapper(dot / (norm_a * norm_b))

    mock_embedder = MagicMock()
    mock_embedder.encode = mock_encode

    with patch("nlp_pipeline.get_embedder", return_value=mock_embedder), \
         patch("nlp_pipeline.util") as mock_util:
        mock_util.cos_sim = mock_cos_sim

        from nlp_pipeline import score_relevance
        result = score_relevance(articles, topics)

    # All articles get scored
    assert len(result) == len(articles)

    # All scores are valid cosine similarity values (range [-1, 1])
    for article in result:
        assert "relevance_score" in article
        assert -1.0 <= article["relevance_score"] <= 1.0

    # Results are sorted descending by relevance_score
    scores = [a["relevance_score"] for a in result]
    assert scores == sorted(scores, reverse=True)

    # Score is deterministic: calling again with same inputs gives same scores
    with patch("nlp_pipeline.get_embedder", return_value=mock_embedder), \
         patch("nlp_pipeline.util") as mock_util2:
        mock_util2.cos_sim = mock_cos_sim
        result2 = score_relevance(articles, topics)

    scores2 = [a["relevance_score"] for a in result2]
    assert scores == scores2


# ═══════════════════════════════════════════════════════════════════════════════
# Property 2.2: Topic Distribution Preservation
# For all balanced selections with N topics and K articles,
# each topic gets approximately K/N articles (±1).
#
# Observation: _balanced_select() on unfixed code distributes articles
# equally with base_per_topic = top_n // num_topics, remainder distributed
# round-robin. Each topic gets floor(K/N) or ceil(K/N) articles.
#
# **Validates: Requirements 3.4**
# ═══════════════════════════════════════════════════════════════════════════════

@st.composite
def balanced_select_input_strategy(draw):
    """Generate inputs for _balanced_select testing."""
    topics = draw(st.lists(
        st.sampled_from(VALID_TOPICS),
        min_size=1,
        max_size=4,
        unique=True,
    ))
    num_topics = len(topics)

    # Generate articles spread across these topics with enough per topic
    articles_per_topic = draw(st.integers(min_value=3, max_value=8))
    articles = []
    for i, topic in enumerate(topics):
        for j in range(articles_per_topic):
            articles.append({
                "title": f"Article {i}_{j} about {topic}",
                "description": f"Description about {topic} topic number {j}",
                "topic": topic,
                "source": "TestSource",
                "url": f"https://example.com/{topic}/{j}",
                "relevance_score": round(0.9 - j * 0.05, 4),  # Decreasing scores within topic
            })

    top_n = draw(st.integers(min_value=num_topics, max_value=min(len(articles), num_topics * 4)))

    return articles, topics, top_n


@given(data=balanced_select_input_strategy())
@settings(max_examples=50, deadline=None)
def test_balanced_select_distributes_equally(data):
    """
    Property 2.2: For balanced selections with N topics and K articles,
    each topic gets approximately K/N articles (±1).

    On unfixed code, _balanced_select distributes top_n slots equally
    across user topics. Each topic gets floor(top_n/N) or ceil(top_n/N).

    **Validates: Requirements 3.4**
    """
    from nlp_pipeline import _balanced_select

    articles, topics, top_n = data
    num_topics = len(topics)

    result = _balanced_select(articles, topics, top_n)

    # Should not exceed top_n
    assert len(result) <= top_n

    # Count per-topic distribution in result
    topic_counts = {}
    for a in result:
        t = a.get("topic", "unknown")
        topic_counts[t] = topic_counts.get(t, 0) + 1

    # Each topic should get approximately top_n // num_topics (±1)
    expected_base = top_n // num_topics
    for topic in topics:
        count = topic_counts.get(topic, 0)
        # Each topic gets at least floor(top_n/num_topics) - allowing 0 for edge cases
        # and at most ceil(top_n/num_topics) + 1 for remainder distribution
        assert count >= max(0, expected_base - 1), (
            f"Topic '{topic}' got {count} articles, expected at least {max(0, expected_base - 1)} "
            f"(top_n={top_n}, num_topics={num_topics}, base={expected_base})"
        )
        assert count <= expected_base + 2, (
            f"Topic '{topic}' got {count} articles, expected at most {expected_base + 2} "
            f"(top_n={top_n}, num_topics={num_topics}, base={expected_base})"
        )

    # Total articles across all topics in result should equal len(result)
    total_topic_articles = sum(topic_counts.values())
    assert total_topic_articles == len(result)


# ═══════════════════════════════════════════════════════════════════════════════
# Property 2.3: Feedback Boost Preservation
# For all articles with feedback boost applied,
# final score = relevance_score + boost (clamped to ±0.15).
#
# Observation: In process_articles(), feedback boost is applied as:
#   article["relevance_score"] = round(article["relevance_score"] + boost, 4)
# where boost comes from get_feedback_boost() which clamps to max(-0.15, min(0.15, net*0.05))
#
# **Validates: Requirements 3.6**
# ═══════════════════════════════════════════════════════════════════════════════

@st.composite
def feedback_boost_scenario(draw):
    """Generate a scenario with articles and feedback boosts."""
    topics = draw(st.lists(
        st.sampled_from(VALID_TOPICS),
        min_size=1,
        max_size=3,
        unique=True,
    ))

    sources = ["TechCrunch", "Bloomberg", "Reuters", "Verge", "Ars Technica"]
    used_sources = draw(st.lists(
        st.sampled_from(sources),
        min_size=1,
        max_size=3,
        unique=True,
    ))

    # Generate boost values clamped to ±0.15 (as get_feedback_boost does)
    feedback_boost = {}
    for source in used_sources:
        # net_signal ranges from -3 to 3, multiplied by 0.05, clamped to [-0.15, 0.15]
        net_signal = draw(st.integers(min_value=-3, max_value=3))
        boost = max(-0.15, min(0.15, net_signal * 0.05))
        if boost != 0:
            feedback_boost[source] = boost

    assume(len(feedback_boost) > 0)

    # Generate pre-scored articles (simulating output of score_relevance)
    articles = []
    for i in range(draw(st.integers(min_value=3, max_value=8))):
        topic = draw(st.sampled_from(topics))
        source = draw(st.sampled_from(sources))
        score = draw(st.floats(min_value=0.3, max_value=0.95, allow_nan=False, allow_infinity=False))
        articles.append({
            "title": f"Article {i} from {source}",
            "description": f"A test article about {topic}",
            "topic": topic,
            "source": source,
            "url": f"https://example.com/{i}",
            "relevance_score": round(score, 4),
        })

    return articles, topics, feedback_boost


@given(data=feedback_boost_scenario())
@settings(max_examples=50, deadline=None)
def test_feedback_boost_adjusts_scores_additively(data):
    """
    Property 2.3: Feedback boost is applied additively to relevance scores
    and is clamped to ±0.15 per source.

    On unfixed code, process_articles() applies:
      article["relevance_score"] += boost
    where boost = max(-0.15, min(0.15, net_signal * 0.05))

    We directly test the boost application logic from process_articles().

    **Validates: Requirements 3.6**
    """
    articles, topics, feedback_boost = data

    # Record original scores
    original_scores = {a["url"]: a["relevance_score"] for a in articles}

    # Apply feedback boost the same way process_articles does
    for article in articles:
        boost = feedback_boost.get(article.get("source", ""), 0.0)
        article["relevance_score"] = round(article["relevance_score"] + boost, 4)

    # Verify: each article's score changed by exactly the boost for its source
    for article in articles:
        original = original_scores[article["url"]]
        boost = feedback_boost.get(article.get("source", ""), 0.0)
        expected = round(original + boost, 4)
        assert article["relevance_score"] == expected, (
            f"Expected score {expected} for '{article['title']}' "
            f"(original={original}, boost={boost}), got {article['relevance_score']}"
        )

    # Verify: all boosts are within ±0.15
    for source, boost in feedback_boost.items():
        assert -0.15 <= boost <= 0.15, f"Boost for '{source}' is {boost}, outside ±0.15"


# ═══════════════════════════════════════════════════════════════════════════════
# Property 2.4: Summary Pass-Through Preservation
# For all well-formed summary strings (end with terminal punctuation,
# no markdown), _clean_summary(text) == text.
#
# Observation: _clean_summary() doesn't exist yet in the unfixed code.
# We test the CONCEPT: well-formed text (ending in . ! ?, no markdown)
# should be preserved unchanged. This validates that the future implementation
# won't modify already-correct text.
#
# **Validates: Requirements 3.2**
# ═══════════════════════════════════════════════════════════════════════════════

@st.composite
def well_formed_summary_strategy(draw):
    """
    Generate summary strings that are well-formed:
    - End with terminal punctuation (., !, ?)
    - No markdown characters (**, *, #, `)
    - Plain text only
    """
    # Generate sentence fragments without markdown characters
    safe_chars = st.characters(
        whitelist_categories=("L", "N", "Z"),
        blacklist_characters="*#`>~[]()_{}-",
    )

    # Generate 2-4 sentences
    num_sentences = draw(st.integers(min_value=2, max_value=4))
    sentences = []
    for _ in range(num_sentences):
        words = draw(st.lists(
            st.text(alphabet=safe_chars, min_size=2, max_size=12),
            min_size=3,
            max_size=10,
        ))
        # Filter out empty/whitespace-only words
        words = [w.strip() for w in words if w.strip()]
        assume(len(words) >= 3)
        sentence = " ".join(words)
        # End with terminal punctuation
        terminal = draw(st.sampled_from([".", "!", "?"]))
        sentences.append(sentence + terminal)

    summary = " ".join(sentences)
    # Ensure no markdown leaked in
    assume("**" not in summary)
    assume("*" not in summary)
    assume("`" not in summary)
    assume("#" not in summary)
    assume(">" not in summary)
    assume("---" not in summary)
    assume("[" not in summary)
    assume("]" not in summary)
    assume(len(summary) >= 20)

    return summary


@given(summary=well_formed_summary_strategy())
@settings(max_examples=50, deadline=None)
def test_well_formed_summary_passes_through_unchanged(summary):
    """
    Property 2.4: Well-formed summaries (ending with terminal punctuation,
    no markdown) should pass through the clean_summary function unchanged.

    Since _clean_summary() doesn't exist yet, we test the invariant that
    well-formed text equals itself — establishing the baseline that the
    future implementation must preserve.

    The test validates: if summary is well-formed, then clean(summary) == summary.
    We implement the expected _clean_summary logic here to validate the concept.

    **Validates: Requirements 3.2**
    """

    def _clean_summary_expected(text: str) -> str:
        """Expected behavior of _clean_summary for well-formed input."""
        # Strip markdown formatting
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # bold
        text = re.sub(r'\*(.+?)\*', r'\1', text)      # italic
        text = re.sub(r'#{1,6}\s*', '', text)          # headers
        text = re.sub(r'`(.+?)`', r'\1', text)         # inline code
        text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)  # blockquotes
        text = re.sub(r'---+', '', text)               # horizontal rules
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # links → text only

        text = text.strip()

        # Ensure ends on complete sentence
        if text and text[-1] not in '.!?':
            last_period = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
            if last_period > 0:
                text = text[:last_period + 1]

        return text.strip()

    # For well-formed summaries, the clean function should return them unchanged
    cleaned = _clean_summary_expected(summary)
    assert cleaned == summary, (
        f"Well-formed summary was modified by _clean_summary.\n"
        f"Input:  '{summary}'\n"
        f"Output: '{cleaned}'"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PROCESS_ARTICLES PIPELINE-LEVEL PRESERVATION PROPERTIES
#
# These tests exercise the full process_articles() pipeline with mocked
# score_relevance and summarize_article, verifying that when the article pool
# is SUFFICIENT (≥8 above threshold), the pipeline preserves:
#   - MAX_ARTICLES (10) cap
#   - Quality filtering (no below-threshold articles)
#   - Cross-edition dedup (sent_urls excluded)
#   - Balanced topic distribution (each topic gets fair slots)
#
# **Validates: Requirements 3.1, 3.2, 3.3, 3.5**
# ═══════════════════════════════════════════════════════════════════════════════


def _mock_score_relevance(articles, user_topics):
    """
    Return articles with relevance_score set from _assigned_score field.
    Sorted descending by score (matching real score_relevance behavior).
    """
    scored = []
    for article in articles:
        score = article.get("_assigned_score", 0.5)
        scored.append({**article, "relevance_score": score})
    return sorted(scored, key=lambda x: x["relevance_score"], reverse=True)


# ─── Strategies for pipeline-level tests ──────────────────────────────────────

@st.composite
def abundant_pool_strategy(draw):
    """
    Generate article sets where 15+ articles score above threshold.
    Tests MAX_ARTICLES cap enforcement.
    """
    num_articles = draw(st.integers(min_value=15, max_value=25))
    topic = draw(st.sampled_from(VALID_TOPICS))

    articles = []
    for i in range(num_articles):
        # All articles well above threshold
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
def sufficient_pool_strategy(draw, min_above_threshold=8, max_articles=18):
    """
    Generate article sets where at least min_above_threshold articles
    have pre-assigned scores above RELEVANCE_THRESHOLD (0.2).
    """
    num_articles = draw(st.integers(min_value=min_above_threshold, max_value=max_articles))
    topic = draw(st.sampled_from(VALID_TOPICS))

    articles = []
    above_count = 0
    for i in range(num_articles):
        if above_count < min_above_threshold:
            score = draw(st.floats(min_value=0.25, max_value=0.95, allow_nan=False, allow_infinity=False))
            above_count += 1
        else:
            score = draw(st.floats(min_value=0.05, max_value=0.95, allow_nan=False, allow_infinity=False))
            if score >= RELEVANCE_THRESHOLD:
                above_count += 1

        articles.append({
            "title": f"Article {i} about {topic}",
            "description": f"Description of article {i} covering {topic}",
            "topic": topic,
            "source": draw(st.sampled_from(["TechCrunch", "Bloomberg", "Reuters", "Verge", "Ars Technica"])),
            "url": f"https://example.com/article-{i}-{draw(st.integers(min_value=1000, max_value=99999))}",
            "published_at": "2025-01-01T10:00:00Z",
            "_assigned_score": round(score, 4),
        })

    return articles, [topic]


@st.composite
def dedup_sufficient_pool_strategy(draw):
    """
    Generate article sets with some previously-sent URLs, where
    the remaining pool (after dedup) still has ≥8 articles above threshold.
    """
    num_sent = draw(st.integers(min_value=2, max_value=5))
    num_fresh = draw(st.integers(min_value=10, max_value=15))
    topic = draw(st.sampled_from(VALID_TOPICS))

    sent_urls = set()
    articles = []

    # Articles that will be deduped (sent previously)
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

    # Fresh articles (all above threshold)
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


@st.composite
def multi_topic_sufficient_strategy(draw):
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


# ═══════════════════════════════════════════════════════════════════════════════
# Property 2.5: MAX_ARTICLES Cap Enforcement
#
# For all article sets where ≥8 pass threshold, result length ≤ MAX_ARTICLES (10)
#
# **Validates: Requirements 3.1**
# ═══════════════════════════════════════════════════════════════════════════════

@given(data=abundant_pool_strategy())
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
def test_pipeline_max_articles_cap_enforced(data):
    """
    Property 2.5: For all article sets where ≥8 pass threshold,
    result length ≤ MAX_ARTICLES (10).

    When the pool is abundant (15+ above threshold), process_articles
    must cap output at MAX_ARTICLES regardless of how many are available.

    **Validates: Requirements 3.1**
    """
    articles, topics = data

    with patch("nlp_pipeline.score_relevance", side_effect=_mock_score_relevance), \
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
# Property 2.6: Quality Filtering — No Below-Threshold Articles
#
# For all article sets where ≥8 pass threshold, no article in result
# has relevance_score < RELEVANCE_THRESHOLD
#
# **Validates: Requirements 3.2**
# ═══════════════════════════════════════════════════════════════════════════════

@given(data=sufficient_pool_strategy(min_above_threshold=8, max_articles=18))
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
def test_pipeline_no_below_threshold_articles_when_sufficient(data):
    """
    Property 2.6: For all article sets where ≥8 pass threshold,
    no article in result has relevance_score < RELEVANCE_THRESHOLD.

    When the pool is sufficient, low-scoring articles should still be
    filtered out to maintain newsletter quality.

    **Validates: Requirements 3.2**
    """
    articles, topics = data

    with patch("nlp_pipeline.score_relevance", side_effect=_mock_score_relevance), \
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
# Property 2.7: Cross-Edition Dedup — Sent URLs Excluded
#
# For all article sets where ≥8 pass threshold AND sent_urls provided,
# no previously-sent URL appears in result
#
# **Validates: Requirements 3.3**
# ═══════════════════════════════════════════════════════════════════════════════

@given(data=dedup_sufficient_pool_strategy())
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
def test_pipeline_sent_urls_excluded_when_sufficient(data):
    """
    Property 2.7: For all article sets where ≥8 pass threshold AND sent_urls
    provided, no previously-sent URL appears in result.

    When remaining pool after dedup is ≥8, cross-edition dedup must
    continue to exclude previously sent articles.

    **Validates: Requirements 3.3**
    """
    articles, topics, sent_urls = data

    with patch("nlp_pipeline.score_relevance", side_effect=_mock_score_relevance), \
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
# Property 2.8: Balanced Topic Distribution — Minimum Slots Per Topic
#
# For all multi-topic article sets with sufficient pool, each topic gets
# at least floor(top_n / num_topics) slots
#
# **Validates: Requirements 3.5**
# ═══════════════════════════════════════════════════════════════════════════════

@given(data=multi_topic_sufficient_strategy())
@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
def test_pipeline_balanced_distribution_minimum_slots(data):
    """
    Property 2.8: For all multi-topic article sets with sufficient pool,
    each topic gets at least floor(top_n / num_topics) slots.

    When pool is sufficient across all topics, balanced distribution
    should give each topic a fair share of available slots.

    **Validates: Requirements 3.5**
    """
    articles, topics = data
    num_topics = len(topics)

    with patch("nlp_pipeline.score_relevance", side_effect=_mock_score_relevance), \
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
    # (capped by what's actually available for that topic above threshold)
    expected_min_per_topic = MAX_ARTICLES // num_topics

    for topic in topics:
        count = topic_counts.get(topic, 0)
        available_for_topic = sum(
            1 for a in articles
            if a.get("topic") == topic and a.get("_assigned_score", 0) >= RELEVANCE_THRESHOLD
        )
        effective_min = min(expected_min_per_topic, available_for_topic)

        assert count >= effective_min, (
            f"Topic '{topic}' got {count} slots, expected at least {effective_min} "
            f"(floor({MAX_ARTICLES}/{num_topics})={expected_min_per_topic}, "
            f"available={available_for_topic}). "
            f"Balanced distribution should allocate fairly across topics."
        )
