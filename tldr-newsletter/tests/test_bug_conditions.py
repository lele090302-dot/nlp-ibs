"""
Bug Condition Exploration Tests — Newsletter Quality Bugs

These property-based tests encode the EXPECTED (correct) behavior for four bugs:
1. Freshness: Stale articles (>3 days old) should be excluded
2. Summary quality: Summaries should end with terminal punctuation, no markdown
3. Email size: Newsletter HTML should not exceed 102,000 bytes
4. Deduplication: Previously sent URLs should not appear in output

On UNFIXED code, these tests are EXPECTED TO FAIL — failure confirms the bugs exist.
After implementing fixes, these same tests should PASS.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
"""

import sys
import os
import inspect
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock out heavy ML dependencies before importing project modules
# This avoids loading sentence_transformers/torch which have version issues
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
from fetcher import fetch_from_newsapi, fetch_from_rss
from nlp_pipeline import summarize_article, process_articles
from newsletter_builder import build_html


# ─── Strategies ───────────────────────────────────────────────────────────────

def article_strategy(min_age_days=4, max_age_days=30):
    """Generate articles with published_at older than 3 days."""
    return st.fixed_dictionaries({
        "title": st.text(min_size=10, max_size=80, alphabet=st.characters(
            whitelist_categories=("L", "N", "P", "Z"),
            whitelist_characters=" ",
        )),
        "url": st.from_regex(r"https://example\.com/article/[a-z0-9]{8}", fullmatch=True),
        "source": st.sampled_from(["TechCrunch", "VentureBeat", "ArsTechnica", "TheVerge"]),
        "published_at": st.integers(
            min_value=min_age_days, max_value=max_age_days
        ).map(lambda days: (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()),
        "description": st.text(min_size=50, max_size=300, alphabet=st.characters(
            whitelist_categories=("L", "N", "P", "Z"),
            whitelist_characters=" .",
        )),
        "content": st.text(min_size=100, max_size=500, alphabet=st.characters(
            whitelist_categories=("L", "N", "P", "Z"),
            whitelist_characters=" .",
        )),
        "topic": st.sampled_from(["GenAI", "Fintech", "Tech", "Startups", "Crypto"]),
    })


# ─── Bug 1: Freshness — No date filtering exists ─────────────────────────────
# Validates: Requirements 1.1, 1.2

class TestFreshnessFiltering:
    """
    Confirms that fetch_from_newsapi() and fetch_from_rss() do NOT filter by date.

    Expected behavior (after fix): stale articles (> 3 days old) should be excluded.
    Current behavior (unfixed): no date filtering exists, so these tests FAIL.
    """

    def test_newsapi_has_no_from_parameter(self):
        """
        Validates: Requirements 1.1

        Verify that fetch_from_newsapi passes a 'from' date parameter
        to the NewsAPI request. This will FAIL on unfixed code because
        no 'from' param is passed — stale articles can be returned.
        """
        with patch("fetcher.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"articles": []}
            mock_get.return_value = mock_response

            # Temporarily set a fake API key
            with patch("fetcher.NEWS_API_KEY", "fake-key-for-test"):
                fetch_from_newsapi("GenAI")

            # Check the params that were passed to requests.get
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args
            params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", {})

            # ASSERT: 'from' parameter SHOULD exist (expected behavior)
            # This will FAIL on unfixed code because no 'from' param is passed
            assert "from" in params, (
                "fetch_from_newsapi() does not pass a 'from' date parameter to NewsAPI. "
                "Stale articles of any age can be returned. Bug 1.1 confirmed."
            )

    @given(data=st.data())
    @settings(max_examples=5, deadline=None)
    def test_rss_does_not_filter_by_date(self, data):
        """
        Validates: Requirements 1.2

        Verify that fetch_from_rss accepts a freshness_days parameter.
        This will FAIL on unfixed code because the parameter doesn't exist.
        """
        # Inspect the function signature for a freshness_days parameter
        sig = inspect.signature(fetch_from_rss)
        param_names = list(sig.parameters.keys())

        # ASSERT: fetch_from_rss SHOULD accept a freshness_days parameter
        # This will FAIL on unfixed code because the parameter doesn't exist
        assert "freshness_days" in param_names, (
            "fetch_from_rss() does not accept a 'freshness_days' parameter. "
            "No date filtering logic exists — arbitrarily old articles pass through. "
            "Bug 1.2 confirmed."
        )


# ─── Bug 2: Summary Quality — Truncation and markdown ────────────────────────
# Validates: Requirements 1.4, 1.5

class TestSummaryQuality:
    """
    Confirms that summarize_article() can produce truncated summaries with markdown.

    Expected behavior (after fix): summaries always end with terminal punctuation
    and contain no markdown formatting.
    Current behavior (unfixed): max_tokens=120 causes truncation, no post-processing.
    """

    @given(data=st.data())
    @settings(max_examples=5, deadline=None)
    def test_summary_ends_with_terminal_punctuation(self, data):
        """
        Validates: Requirements 1.4

        Mock the LLM to return a truncated response (simulating max_tokens=120 cutoff).
        Assert that summarize_article output ends with terminal punctuation.
        This will FAIL because no _clean_summary() post-processing exists.
        """
        # Simulate truncated LLM outputs (what happens with max_tokens=120)
        # Each must contain at least one sentence boundary (.!?) so _clean_summary can truncate
        truncated_responses = [
            "OpenAI announced a new reasoning model that can solve complex math problems. The model, called o3, achieves state-of-the-art results on benchm",
            "Apple released iOS 18.2 with major AI features. The redesigned Siri can understand context better and provide more relev",
            "Microsoft reported quarterly earnings that beat analyst expectations. The company's cloud division Azure grew by 29% year-over-year, driven by increased dema",
            "Google DeepMind published research showing their new AlphaFold 3 model can predict protein structures with unprecedented accuracy. The implications for drug disc",
            "The Federal Reserve announced it would hold interest rates steady. Ongoing concerns about inflation remaining above the 2% target despite recent",
        ]

        response_text = data.draw(st.sampled_from(truncated_responses))

        article = {
            "title": "Test Article About Technology",
            "content": "A long article about technology and its impact on society. " * 20,
            "description": "Technology article description",
        }

        # Mock the Groq client to return our truncated response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = response_text

        with patch("nlp_pipeline.get_groq_client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_instance

            result = summarize_article(article)

        # ASSERT: Summary SHOULD end with terminal punctuation (.!?)
        # This will FAIL on unfixed code because truncated text is returned as-is
        assert result and result[-1] in ".!?", (
            f"Summary does not end with terminal punctuation: ...'{result[-60:]}'. "
            f"Truncation at max_tokens=120 produces incomplete sentences. "
            f"Bug 1.4 confirmed."
        )

    @given(data=st.data())
    @settings(max_examples=5, deadline=None)
    def test_summary_contains_no_markdown(self, data):
        """
        Validates: Requirements 1.5

        Mock the LLM to return responses with markdown formatting.
        Assert that summarize_article output contains no markdown characters.
        This will FAIL because no post-processing strips markdown.
        """
        # Simulate LLM responses that contain markdown (common LLM behavior)
        markdown_responses = [
            "**Breaking:** Apple released iOS 18.2 with *major* AI features including a redesigned Siri.",
            "The company's `GPT-4o` model represents a **significant leap** in multimodal AI capabilities.",
            "# Key Takeaway\nGoogle's new chip achieves *remarkable* performance gains over previous generations.",
            "Microsoft's **Azure** cloud division grew by 29%, driven by `AI workloads` and enterprise demand.",
            "The startup raised **$50M** in Series B funding to expand its *innovative* platform globally.",
        ]

        response_text = data.draw(st.sampled_from(markdown_responses))

        article = {
            "title": "Test Article",
            "content": "Article content about tech industry developments." * 10,
            "description": "Tech industry article",
        }

        # Mock the Groq client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = response_text

        with patch("nlp_pipeline.get_groq_client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.chat.completions.create.return_value = mock_response
            mock_client.return_value = mock_instance

            result = summarize_article(article)

        # ASSERT: Summary SHOULD NOT contain markdown characters
        # This will FAIL on unfixed code because no stripping occurs
        markdown_chars = ["**", "`", "# "]
        found_markdown = [ch for ch in markdown_chars if ch in result]
        assert not found_markdown, (
            f"Summary contains markdown characters {found_markdown}: '{result[:100]}'. "
            f"No post-processing strips markdown from LLM output. "
            f"Bug 1.5 confirmed."
        )


# ─── Bug 3: Email Size — No size guard exists ────────────────────────────────
# Validates: Requirements 1.6

class TestEmailSize:
    """
    Confirms that build_html() has no size guard — it renders ALL articles
    regardless of total HTML size, which can exceed Gmail's 102KB clip limit
    when articles have longer summaries or many articles are included.

    Expected behavior (after fix): build_html() accepts a max_bytes parameter
    and drops articles to stay under the limit.
    Current behavior (unfixed): no max_bytes parameter, no size management.
    """

    def test_build_html_has_no_size_guard_parameter(self):
        """
        Validates: Requirements 1.6

        Verify that build_html() accepts a 'max_bytes' parameter for size control.
        This will FAIL on unfixed code because no size guard exists.
        """
        sig = inspect.signature(build_html)
        param_names = list(sig.parameters.keys())

        # ASSERT: build_html SHOULD accept a 'max_bytes' parameter
        # This will FAIL on unfixed code — no size management exists
        assert "max_bytes" in param_names, (
            "build_html() does not accept a 'max_bytes' parameter. "
            "No size guard exists — the system renders all articles regardless of total "
            "HTML size, risking Gmail's 102KB clip limit. Bug 1.6 confirmed."
        )

    @given(data=st.data())
    @settings(max_examples=5, deadline=None)
    def test_newsletter_html_under_102kb_with_large_content(self, data):
        """
        Validates: Requirements 1.6

        Build a newsletter with many articles containing long summaries and URLs.
        Since build_html() has no max_bytes parameter, the HTML size is unbounded.
        With 10 articles and ~8500-char summaries (which is possible with
        max_tokens=250 and verbose LLM responses), HTML exceeds 102KB.
        This will FAIL because build_html renders everything without checking size.
        """
        # Generate 10 articles with very long summaries.
        # With max_tokens=250, the LLM can produce much longer text. If the LLM
        # is verbose (which happens), summaries of ~800-900 tokens (~5000-8000 chars)
        # are possible before the token limit cuts. 10 such articles overflow.
        articles = []
        for i in range(10):
            # Each summary ~8500 chars to push the total past 102KB
            # This simulates worst-case LLM verbosity (happens in practice with
            # certain articles that trigger long explanations)
            summary = (
                "According to industry analysts at Goldman Sachs and Morgan Stanley, "
                "this development represents a significant milestone in the ongoing "
                "transformation of the enterprise technology sector and its approach "
                "to artificial intelligence integration across cloud platforms. "
            ) * data.draw(st.integers(min_value=30, max_value=35))

            url = (
                f"https://www.example-tech-publication.com/2024/01/"
                f"major-technology-corporation-announces-revolutionary-platform-{i}/"
                f"?utm_source=newsletter&utm_medium=email&utm_campaign=daily"
                f"&utm_content=position{i}&ref=tldr&subscriber_id=12345"
            )

            feedback_url = (
                f"http://newsletter-app.enterprise-company.com:8501/api/feedback"
                f"?email=enterprise.subscriber%40very-long-company-domain-name.com"
                f"&url=https%3A%2F%2Fwww.example-tech-publication.com%2F2024%2F01%2F"
                f"major-technology-corporation-platform-{i}%2F"
                f"&source=TechCrunch%20International&topic=GenAI"
            )

            articles.append({
                "title": f"Breaking Analysis {i+1}: Major Technology Corporation Announces Revolutionary AI Platform That Promises Complete Industry Transformation Across All Sectors",
                "url": url,
                "source": "TechCrunch International Business & Technology",
                "topic": data.draw(st.sampled_from(["GenAI", "Fintech", "Tech", "Startups", "Crypto"])),
                "summary": summary,
                "reading_time": 7,
                "relevance_score": 0.85,
                "feedback_up_url": feedback_url + "&signal=1",
                "feedback_down_url": feedback_url + "&signal=-1",
            })

        html = build_html(
            user_name="Enterprise Technology Professional",
            user_email="subscriber.user@enterprise-company.com",
            topics=["GenAI", "Tech", "Fintech", "Startups", "Crypto"],
            articles=articles,
        )

        html_bytes = len(html.encode("utf-8"))

        # ASSERT: HTML SHOULD be under 102,000 bytes (Gmail clip limit)
        # This will FAIL on unfixed code because no size guard exists to drop articles
        assert html_bytes <= 102_000, (
            f"Newsletter HTML is {html_bytes:,} bytes, exceeding Gmail's 102,000 byte "
            f"clip limit. The system renders all {len(articles)} articles regardless of total size. "
            f"Bug 1.6 confirmed."
        )


# ─── Bug 4: Deduplication — No cross-edition dedup exists ────────────────────
# Validates: Requirements 1.7

class TestDeduplication:
    """
    Confirms that process_articles() does not filter by previously sent URLs.

    Expected behavior (after fix): process_articles accepts sent_urls and excludes them.
    Current behavior (unfixed): no sent_urls parameter exists.
    """

    def test_process_articles_accepts_sent_urls_parameter(self):
        """
        Validates: Requirements 1.7

        Verify that process_articles() accepts a 'sent_urls' parameter.
        This will FAIL on unfixed code because the parameter doesn't exist
        or is never used for filtering.
        """
        sig = inspect.signature(process_articles)
        param_names = list(sig.parameters.keys())

        # ASSERT: process_articles SHOULD accept a 'sent_urls' parameter
        # This will FAIL on unfixed code — no dedup parameter exists
        assert "sent_urls" in param_names, (
            "process_articles() does not accept a 'sent_urls' parameter. "
            "No mechanism exists to exclude previously sent articles. "
            "Bug 1.7 confirmed."
        )

    @given(
        sent_urls=st.frozensets(
            st.from_regex(r"https://example\.com/sent/[a-z0-9]{6}", fullmatch=True),
            min_size=2,
            max_size=5,
        ),
    )
    @settings(max_examples=5, deadline=None)
    def test_sent_urls_excluded_from_output(self, sent_urls):
        """
        Validates: Requirements 1.7

        Create an article pool where some URLs are in the sent_urls set.
        Call process_articles and verify none of the sent URLs appear in output.
        This will FAIL because process_articles ignores sent_urls entirely.
        """
        sent_urls_set = set(sent_urls)

        # Build articles — some with URLs from sent_urls, some fresh
        articles = []
        for i, url in enumerate(sent_urls_set):
            articles.append({
                "title": f"Previously Sent Article {i}",
                "url": url,
                "source": "TechCrunch",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "description": "This article was already sent in a previous edition.",
                "content": "Full content of the previously sent article. " * 10,
                "topic": "GenAI",
            })

        # Add some fresh articles that should be kept
        for i in range(5):
            articles.append({
                "title": f"New Article {i}",
                "url": f"https://example.com/new/{i:06d}",
                "source": "VentureBeat",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "description": "A fresh article not previously sent to this user.",
                "content": "Fresh content about new developments in technology. " * 10,
                "topic": "GenAI",
            })

        # Mock the scoring/summarization since we're testing dedup logic
        with patch("nlp_pipeline.summarize_article") as mock_summarize, \
             patch("nlp_pipeline.score_relevance") as mock_score:

            mock_summarize.return_value = "This is a test summary."

            # Make score_relevance return all articles with high scores
            def fake_score(articles_in, topics):
                return [{**a, "relevance_score": 0.8} for a in articles_in]

            mock_score.side_effect = fake_score

            try:
                result = process_articles(
                    articles=articles,
                    user_topics=["GenAI"],
                    top_n=5,
                    sent_urls=sent_urls_set,
                )
            except TypeError as e:
                # If process_articles doesn't accept sent_urls, the bug is confirmed
                if "sent_urls" in str(e):
                    pytest.fail(
                        f"process_articles() does not accept 'sent_urls' parameter: {e}. "
                        f"Bug 1.7 confirmed — no cross-edition deduplication exists."
                    )
                raise

        # Check that none of the sent URLs appear in the result
        result_urls = {a["url"] for a in result}
        duplicates = result_urls & sent_urls_set

        # ASSERT: No sent URLs should appear in the output
        assert not duplicates, (
            f"Previously sent URLs {duplicates} appear in pipeline output. "
            f"process_articles does not filter by sent_urls. Bug 1.7 confirmed."
        )
