"""
Property-Based Tests for Rephrased Article Titles

Tests for the title rephrasing feature in nlp_pipeline.py.
"""

import sys
import os
import re
from unittest.mock import MagicMock

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

from hypothesis import given, settings, assume, note
from hypothesis import strategies as st

from nlp_pipeline import _clean_title_fallback


# ─── Strategies ───────────────────────────────────────────────────────────────


def plain_text_words():
    """Generate a list of plain text words (no special chars that look like markup)."""
    word = st.from_regex(r"[A-Za-z0-9]{1,12}", fullmatch=True)
    return st.lists(word, min_size=1, max_size=6)


def html_wrapped(words):
    """Wrap words in randomly selected HTML tags."""
    tags = ["b", "em", "strong", "i", "h1", "h2", "h3", "span", "p", "a"]
    tag = st.sampled_from(tags)

    @st.composite
    def strategy(draw):
        w = draw(words)
        content = " ".join(w)
        t = draw(tag)
        return f"<{t}>{content}</{t}>", w

    return strategy()


def markdown_wrapped(words):
    """Wrap words in randomly selected markdown formatting."""
    @st.composite
    def strategy(draw):
        w = draw(words)
        content = " ".join(w)
        fmt = draw(st.sampled_from([
            "bold",
            "italic",
            "header",
            "code",
            "blockquote",
            "link",
        ]))
        if fmt == "bold":
            return f"**{content}**", w
        elif fmt == "italic":
            return f"*{content}*", w
        elif fmt == "header":
            level = draw(st.integers(min_value=1, max_value=6))
            return f"{'#' * level} {content}", w
        elif fmt == "code":
            return f"`{content}`", w
        elif fmt == "blockquote":
            # Blockquote must be at line start to be valid markdown
            return f"\n> {content}", w
        elif fmt == "link":
            return f"[{content}](http://example.com)", w
        return content, w

    return strategy()


def formatted_text_strategy():
    """Generate text with randomly injected HTML and/or markdown formatting."""
    @st.composite
    def strategy(draw):
        words = plain_text_words()
        # Choose a mix of formatting types
        num_segments = draw(st.integers(min_value=1, max_value=3))
        all_plain_words = []
        segments = []

        for _ in range(num_segments):
            fmt_type = draw(st.sampled_from(["html", "markdown"]))
            if fmt_type == "html":
                formatted, plain_w = draw(html_wrapped(words))
                segments.append(formatted)
                all_plain_words.extend(plain_w)
            else:
                formatted, plain_w = draw(markdown_wrapped(words))
                segments.append(formatted)
                all_plain_words.extend(plain_w)

        combined = " ".join(segments)
        return combined, all_plain_words

    return strategy()


# ─── Property Test ────────────────────────────────────────────────────────────


# Feature: rephrased-article-titles, Property 4: HTML and markdown stripping preserves text content
class TestHTMLMarkdownStripping:
    """
    Property 4: HTML and markdown stripping preserves text content

    For any string containing HTML tags or markdown formatting,
    _clean_title_fallback() returns a string with no HTML tags and no
    markdown syntax characters, and the plain text content is preserved.

    **Validates: Requirements 3.2**
    """

    @given(data=formatted_text_strategy())
    @settings(max_examples=100, deadline=None)
    def test_html_markdown_stripping_preserves_text(self, data):
        """
        **Validates: Requirements 3.2**

        For any string with HTML tags or markdown formatting,
        _clean_title_fallback() strips all markup and preserves the
        original plain text content.
        """
        formatted_text, plain_words = data

        assume(len(plain_words) > 0)
        assume(all(len(w) > 0 for w in plain_words))

        result = _clean_title_fallback(formatted_text)

        note(f"Input: {formatted_text!r}")
        note(f"Output: {result!r}")
        note(f"Plain words: {plain_words}")

        # Assert: no HTML tags remain (no <tag> or </tag> patterns)
        assert not re.search(r"<[^>]+>", result), (
            f"Result still contains HTML tags: {result!r} (input was {formatted_text!r})"
        )

        # Assert: no markdown syntax artifacts remain
        # No bold markers (**)
        assert "**" not in result, (
            f"Result still contains '**': {result!r}"
        )
        # No header markers (# at start of line)
        for line in result.split("\n"):
            assert not re.match(r"^#{1,6}\s", line), (
                f"Result still contains markdown header: {line!r}"
            )
        # No backtick code delimiters (single backtick used as formatting)
        assert "`" not in result, (
            f"Result still contains backtick: {result!r}"
        )

        # Assert: original plain text words are preserved in the result
        for word in plain_words:
            assert word in result, (
                f"Plain text word {word!r} not found in result {result!r} "
                f"(input was {formatted_text!r})"
            )


# ─── Property 5 ───────────────────────────────────────────────────────────────

from unittest.mock import patch, MagicMock as MockObj
import importlib

# Feature: rephrased-article-titles, Property 5: Pipeline continuity on rephrasing failure
class TestPipelineContinuityOnFailure:
    """
    Property 5: Pipeline continuity on rephrasing failure

    For any list of articles where the Groq client raises an exception for
    every rephrase call, process_articles() returns the same number of articles,
    each with title, original_title, and reading_time fields.

    **Validates: Requirements 3.3, 3.4**
    """

    @given(
        articles=st.lists(
            st.fixed_dictionaries({
                "title": st.text(
                    alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
                    min_size=3,
                    max_size=50,
                ),
                "url": st.from_regex(r"https://example\.com/[a-z]{3,10}", fullmatch=True),
                "source": st.sampled_from(["TechCrunch", "Ars Technica", "Wired", "The Verge"]),
                "description": st.text(min_size=10, max_size=100),
                "content": st.text(min_size=10, max_size=200),
                "topic": st.sampled_from(["AI", "Tech", "Startups", "Fintech", "Crypto"]),
                "published_at": st.just("2025-01-01T12:00:00Z"),
            }),
            min_size=1,
            max_size=5,
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_pipeline_continuity_on_failure(self, articles):
        """
        **Validates: Requirements 3.3, 3.4**

        For any list of articles where the Groq client raises an exception for
        every rephrase call, process_articles() returns the same number of
        articles, each with title, original_title, and reading_time fields,
        and each original_title matches the input title byte-for-byte.
        """
        import nlp_pipeline

        # Ensure unique URLs to avoid dedup issues
        for i, article in enumerate(articles):
            article["url"] = f"https://example.com/article{i}"

        # Save original titles mapped by URL for later comparison
        original_titles_by_url = {a["url"]: a["title"] for a in articles}

        # Create a mock Groq client that:
        # - Raises exception for rephrase calls (containing REPHRASE_TITLE_PROMPT content)
        # - Returns a valid summary for summarize calls (containing SUMMARIZE_PROMPT content)
        def mock_groq_side_effect(*args, **kwargs):
            messages = kwargs.get("messages", [])
            if messages:
                content = messages[0].get("content", "")
                if "Rewrite the following article headline" in content:
                    raise Exception("API error")
                elif "Summarize the following article" in content:
                    mock_response = MockObj()
                    mock_response.choices = [MockObj()]
                    mock_response.choices[0].message = MockObj()
                    mock_response.choices[0].message.content = "This is a test summary."
                    return mock_response
            # Default: raise for any unknown call
            raise Exception("API error")

        mock_client = MockObj()
        mock_client.chat.completions.create.side_effect = mock_groq_side_effect

        # Mock embedder to return dummy embeddings and high cosine similarity
        mock_embedder_instance = MockObj()
        mock_embedder_instance.encode.return_value = MockObj()

        # cos_sim result needs to support float() conversion (like a 1x1 tensor)
        class FakeScore:
            def __float__(self):
                return 0.95

        with patch.object(nlp_pipeline, "get_groq_client", return_value=mock_client), \
             patch.object(nlp_pipeline, "get_embedder", return_value=mock_embedder_instance), \
             patch.object(nlp_pipeline.util, "cos_sim", return_value=FakeScore()), \
             patch.object(nlp_pipeline, "_fetch_full_article_text", return_value=""):

            result = nlp_pipeline.process_articles(
                articles,
                user_topics=["Tech"],
                top_n=len(articles),
            )

        # Assert: returned list has same length as input (no articles dropped)
        assert len(result) == len(articles), (
            f"Expected {len(articles)} articles, got {len(result)}"
        )

        # Assert: each returned article has title, original_title, and reading_time fields
        for i, article in enumerate(result):
            assert "title" in article, (
                f"Article {i} is missing 'title' field"
            )
            assert "original_title" in article, (
                f"Article {i} is missing 'original_title' field"
            )
            assert "reading_time" in article, (
                f"Article {i} is missing 'reading_time' field"
            )

            # Assert: original_title matches the input title byte-for-byte (lookup by URL)
            url = article["url"]
            expected_original = original_titles_by_url[url]
            assert article["original_title"] == expected_original, (
                f"Article at URL {url} original_title mismatch: "
                f"expected {expected_original!r}, got {article['original_title']!r}"
            )


# ─── Unit Tests for Prompt Content and Integration Ordering ───────────────────


import os
from unittest.mock import patch, MagicMock, call

from nlp_pipeline import REPHRASE_TITLE_PROMPT, process_articles


class TestPromptContentAndIntegrationOrdering:
    """
    Unit tests verifying prompt content requirements and integration ordering.

    **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 1.4, 4.2, 5.1**
    """

    # ── Prompt Content Tests ──────────────────────────────────────────────────

    def test_prompt_includes_100_char_instruction(self):
        """
        **Validates: Requirements 2.1**

        The REPHRASE_TITLE_PROMPT must contain the 100-character limit instruction.
        """
        assert "100" in REPHRASE_TITLE_PROMPT, (
            "REPHRASE_TITLE_PROMPT does not mention '100' (character limit)"
        )

    def test_prompt_includes_anti_clickbait_instruction(self):
        """
        **Validates: Requirements 2.2**

        The REPHRASE_TITLE_PROMPT must instruct against clickbait.
        """
        prompt_lower = REPHRASE_TITLE_PROMPT.lower()
        assert "clickbait" in prompt_lower, (
            "REPHRASE_TITLE_PROMPT does not mention 'clickbait'"
        )

    def test_prompt_includes_no_jargon_instruction(self):
        """
        **Validates: Requirements 2.3**

        The REPHRASE_TITLE_PROMPT must instruct against jargon or abbreviations.
        """
        prompt_lower = REPHRASE_TITLE_PROMPT.lower()
        assert "jargon" in prompt_lower or "abbreviation" in prompt_lower, (
            "REPHRASE_TITLE_PROMPT does not mention 'jargon' or 'abbreviation'"
        )

    def test_prompt_includes_factual_preservation_instruction(self):
        """
        **Validates: Requirements 2.4**

        The REPHRASE_TITLE_PROMPT must instruct to preserve factual meaning.
        """
        prompt_lower = REPHRASE_TITLE_PROMPT.lower()
        assert "factual" in prompt_lower or "named entities" in prompt_lower, (
            "REPHRASE_TITLE_PROMPT does not mention 'factual' or 'named entities'"
        )

    # ── Integration Ordering Test ─────────────────────────────────────────────

    @patch("nlp_pipeline._fetch_full_article_text", return_value="")
    @patch("nlp_pipeline.rephrase_title")
    @patch("nlp_pipeline.summarize_article")
    @patch("nlp_pipeline.score_relevance")
    def test_rephrase_called_after_summarize(
        self, mock_score, mock_summarize, mock_rephrase, mock_fetch_text
    ):
        """
        **Validates: Requirements 1.4**

        In the enrichment loop, rephrase_title() must be called after
        summarize_article() for each article.
        """
        # Setup: one article that passes through scoring/selection
        test_article = {
            "title": "Test Article Title",
            "url": "https://example.com/test",
            "source": "Test Source",
            "description": "A test article",
            "content": "Some content",
            "topic": "AI",
            "published_at": "2024-01-01T00:00:00Z",
            "relevance_score": 0.9,
        }
        mock_score.return_value = [test_article]
        mock_summarize.return_value = "A summary of the article."
        mock_rephrase.side_effect = lambda article: {
            **article,
            "original_title": article["title"],
            "title": "Rephrased Title",
        }

        # Track call order
        call_order = []
        mock_summarize.side_effect = lambda a: (
            call_order.append("summarize") or "A summary."
        )
        mock_rephrase.side_effect = lambda a: (
            call_order.append("rephrase")
            or {**a, "original_title": a["title"], "title": "Rephrased"}
        )

        process_articles([test_article], ["AI"], top_n=1, min_articles=1)

        # Verify both were called
        assert mock_summarize.called, "summarize_article was not called"
        assert mock_rephrase.called, "rephrase_title was not called"

        # Verify order: summarize must come before rephrase
        assert call_order.index("summarize") < call_order.index("rephrase"), (
            f"Expected summarize before rephrase, got order: {call_order}"
        )

    # ── Deduplication Test ────────────────────────────────────────────────────

    def test_dedup_unaffected_by_rephrasing(self):
        """
        **Validates: Requirements 4.2**

        The fetcher's deduplicate() function operates on raw titles before
        any rephrasing occurs. Two articles with the same raw title are
        deduplicated regardless of what rephrased titles might later be generated.
        """
        from fetcher import deduplicate

        articles = [
            {
                "title": "Breaking: AI Achieves New Milestone",
                "url": "https://example.com/article1",
                "source": "Source A",
            },
            {
                "title": "Breaking: AI Achieves New Milestone",
                "url": "https://example.com/article2",
                "source": "Source B",
            },
        ]

        result = deduplicate(articles)

        # The second article should be deduplicated because it has
        # the same normalized title as the first
        assert len(result) == 1, (
            f"Expected 1 article after dedup, got {len(result)}. "
            "Deduplication should operate on raw titles before rephrasing."
        )

    # ── Template Rendering Test ───────────────────────────────────────────────

    def test_template_renders_title_field(self):
        """
        **Validates: Requirements 5.1**

        The newsletter.html template must use the article.title field
        to render each article's title.
        """
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "newsletter.html"
        )
        with open(template_path, "r") as f:
            template_content = f.read()

        assert "article.title" in template_content, (
            "Newsletter template does not reference 'article.title'. "
            "The template must render the rephrased title via {{ article.title }}."
        )
