# Implementation Plan

## Overview

Fix the article delivery minimum guarantee by repairing broken RSS feed infrastructure, improving relevance scoring, and implementing a progressive constraint-relaxation cascade to ensure subscribers receive at least 8 articles per newsletter.

## Tasks

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Minimum Article Delivery Guarantee
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the pipeline delivers fewer than MIN_ARTICLES (8) for niche-topic subscribers
  - **Scoped PBT Approach**: Use Hypothesis to generate article sets where fewer than 8 articles score above RELEVANCE_THRESHOLD (0.2), simulating niche-topic scenarios with broken feeds and narrow scoring
  - Test file: `tldr-newsletter/tests/test_bug_condition.py`
  - Use `hypothesis` with `@given` strategies generating lists of article dicts with relevance scores distributed such that fewer than 8 pass the 0.2 threshold
  - Mock `score_relevance` to return articles with pre-assigned scores (e.g., 4-6 articles above 0.2, rest below)
  - Mock `summarize_article` to return a fixed string (avoid LLM calls)
  - Assert: `len(result) >= 8 OR (all_fallbacks_exhausted AND alert_logged)` — this encodes the Expected Behavior from design
  - Assert: all returned articles have non-empty `title` and non-empty `url`
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists: system delivers <8 articles with no corrective cascade)
  - Document counterexamples found (e.g., "process_articles returns 4 articles when only 4 of 12 score above 0.2, no cascade triggered")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.2, 2.3, 2.4, 2.6_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Sufficient Pool Behavior Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Test file: `tldr-newsletter/tests/test_preservation.py`
  - Observe: run `process_articles` on UNFIXED code with article sets where ≥8 articles score above 0.2 threshold
  - Observe: verify MAX_ARTICLES (10) cap is enforced when pool is abundant (15+ articles above threshold)
  - Observe: verify balanced topic distribution allocates slots fairly across user topics
  - Observe: verify cross-edition dedup excludes previously sent URLs when remaining pool ≥8
  - Observe: verify feedback boost elevates preferred sources in final ranking
  - Write property-based tests using Hypothesis:
    - Property: for all article sets where ≥8 pass threshold, result length ≤ MAX_ARTICLES (10)
    - Property: for all article sets where ≥8 pass threshold, no article in result has `relevance_score < RELEVANCE_THRESHOLD`
    - Property: for all article sets where ≥8 pass threshold AND sent_urls provided, no previously-sent URL appears in result
    - Property: for all multi-topic article sets with sufficient pool, each topic gets at least `floor(top_n / num_topics)` slots
  - Mock `summarize_article` to return fixed string, mock `score_relevance` to use pre-assigned scores
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve — the cascade logic doesn't exist yet so it can't interfere)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Fix fetcher.py - Repair RSS feed infrastructure

  - [x] 3.1 Replace broken RSS feed URLs in RSS_FEEDS dict
    - Remove HTML page URLs that are not valid RSS/Atom feeds:
      - `https://arstechnica.com/ai/` → `https://arstechnica.com/ai/feed/`
      - `https://www.bloomberg.com/ai` → remove
      - `https://www.bloomberg.com/technology` → remove
      - `https://www.bloomberg.com/technology/startups` → remove
      - `https://www.wsj.com/tech/ai` → remove
      - `https://fintechmagazine.com/fintech` → remove
      - `https://fintechmagazine.com/crypto` → remove
      - `https://arstechnica.com/gadgets/` → `https://arstechnica.com/gadgets/feed/`
    - _Bug_Condition: isBugCondition(input) where broken URLs return HTML instead of RSS XML, yielding 0 articles_
    - _Expected_Behavior: All configured feeds return parseable RSS/Atom XML_
    - _Preservation: Valid feeds continue to function identically_
    - _Requirements: 2.1_

  - [x] 3.2 Add bozo flag checking with warning logging
    - After `feedparser.parse()`, check `feed.bozo` flag
    - If `feed.bozo == 1` AND `len(feed.entries) == 0`: log warning with feed URL and `feed.bozo_exception`, skip feed
    - If `feed.bozo == 1` but entries exist: log warning but continue processing entries (partial parse)
    - Use `import logging; logger = logging.getLogger(__name__)` for structured logging
    - _Bug_Condition: feedparser returns bozo=1 with zero entries on broken feeds_
    - _Expected_Behavior: Warning logged identifying broken feed URL and bozo_exception, feed skipped_
    - _Preservation: Valid feeds with bozo=0 continue processing unchanged_
    - _Requirements: 2.7_

  - [x] 3.3 Use requests.get with timeout for RSS fetches
    - Replace direct `feedparser.parse(feed_url)` with `requests.get(feed_url, timeout=10)` followed by `feedparser.parse(response.content)`
    - Handle `requests.exceptions.Timeout` and `requests.exceptions.RequestException` with warning log
    - Match the 10-second timeout already used for NewsAPI calls
    - _Bug_Condition: feedparser.parse(url) has no timeout, slow servers can stall pipeline_
    - _Expected_Behavior: 10-second timeout enforced, timeout raises handled gracefully_
    - _Preservation: Fast-responding feeds behave identically_
    - _Requirements: 2.9_

  - [x] 3.4 Add entry title/URL validation in fetch_from_rss
    - Only append entries where `entry.get("title")` and `entry.get("link")` are non-empty strings
    - Match the validation logic already used in `fetch_from_newsapi`: `if a.get("title") and a.get("url")`
    - _Bug_Condition: Entries with blank title or missing link enter pipeline, producing broken newsletter links_
    - _Expected_Behavior: Only entries with non-empty title AND non-empty link are appended_
    - _Preservation: Entries that already have valid title and link are unaffected_
    - _Requirements: 2.10_

  - [x] 3.5 Fix date field fallback for Atom feeds
    - Change `entry.get("published", "")` to `entry.get("published") or entry.get("updated", "")`
    - This ensures Atom feeds using "updated" instead of "published" get proper date handling
    - Prevents `_recency_decay` from applying 0.7 penalty to fresh articles with valid dates
    - _Bug_Condition: Atom feeds use "updated" field, system only checks "published", stores empty string_
    - _Expected_Behavior: Date fallback chain: published → updated → empty string_
    - _Preservation: Feeds with "published" field continue to use it as before_
    - _Requirements: 2.8_

- [x] 4. Fix nlp_pipeline.py - Improve scoring and enforce minimum

  - [x] 4.1 Broaden TOPIC_DESCRIPTIONS for wider embeddings
    - Expand each topic description with named entities, subcategories, and varied terminology
    - Goal: produce wider semantic embeddings that capture more legitimately relevant articles
    - Example additions for Startups: "Y Combinator, demo day, founders, pitch decks, valuations, bootstrapping, Series A/B/C"
    - Verify descriptions stay factual and domain-accurate
    - _Bug_Condition: Narrow descriptions produce tight embeddings, inflating false negatives at threshold filter_
    - _Expected_Behavior: Richer descriptions improve cosine similarity for legitimately relevant articles_
    - _Preservation: Irrelevant articles should still score low — don't make descriptions so broad they match everything_
    - _Requirements: 2.5_

  - [x] 4.2 Implement progressive threshold cascade in process_articles
    - After initial threshold filter, if `len(filtered) < min_articles`:
      - Step 1: Lower threshold to 0.15, re-filter scored list
      - Step 2: If still < min_articles, lower to 0.10
      - Step 3: If still < min_articles, lower to 0.05
      - Step 4: If still < min_articles, include all scored articles regardless of threshold
    - Log each cascade step with threshold level and resulting count
    - Cascade MUST NOT activate when initial filtering produces ≥ min_articles (preservation)
    - _Bug_Condition: len(filtered) < MIN_ARTICLES after 0.2 threshold, no corrective action taken_
    - _Expected_Behavior: Progressive cascade lowers threshold until min_articles met or all articles included_
    - _Preservation: When ≥ min_articles pass initial threshold, cascade never activates_
    - _Requirements: 2.2, 2.3_

  - [x] 4.3 Raise MIN_ARTICLES default from 5 to 8 in process_articles
    - Change `min_articles: int = 5` parameter default to `min_articles: int = 8`
    - Ensure all callers are compatible with new default
    - _Requirements: 2.2_

- [x] 5. Fix pipeline.py - Post-filter freshness widening and alert logging

  - [x] 5.1 Raise MIN_ARTICLES constant from 5 to 8
    - Change `MIN_ARTICLES = 5` to `MIN_ARTICLES = 8` in pipeline.py
    - _Requirements: 2.2_

  - [x] 5.2 Implement post-filter freshness widening in send_pipeline
    - Move freshness check to AFTER scoring/filtering (not just after raw fetch)
    - If post-filter count < MIN_ARTICLES after threshold cascade:
      - Widen freshness from 5 → 7 days, re-fetch, re-score, re-filter
      - If still < MIN_ARTICLES, widen to 10 days
    - This ensures widening addresses the post-scoring deficit, not just raw article count
    - _Bug_Condition: Current widening checks raw_articles count before scoring, misses post-filter deficit_
    - _Expected_Behavior: Freshness widening triggered by post-filter count, not raw count_
    - _Preservation: When post-filter count ≥ MIN_ARTICLES, no widening occurs_
    - _Requirements: 2.3, 2.4_

  - [x] 5.3 Add alert logging when minimum cannot be met
    - When all fallback strategies exhausted (cascade + freshness widening) and count still < MIN_ARTICLES:
      - Log explicit alert via `logging.warning()` with: final count, minimum target, strategies attempted, subscriber email/topics
      - Deliver all available articles (even if below minimum)
    - _Bug_Condition: All strategies exhausted, count still below minimum_
    - _Expected_Behavior: Alert logged with details, all available articles delivered_
    - _Preservation: Normal pipeline runs (sufficient articles) produce no alert_
    - _Requirements: 2.6_

- [x] 6. Verify fixes with exploration and preservation tests

  - [x] 6.1 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Minimum Article Delivery Guarantee
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior (delivers ≥8 OR logs alert)
    - When this test passes, it confirms the progressive cascade and fallback strategies work correctly
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed — cascade delivers ≥8 articles or logs alert when exhausted)
    - _Requirements: 2.2, 2.3, 2.4, 2.6_

  - [x] 6.2 Verify preservation tests still pass
    - **Property 2: Preservation** - Sufficient Pool Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions — MAX_ARTICLES cap, quality filtering, dedup, balanced distribution all unchanged)
    - Confirm all tests still pass after fix (no regressions)

- [x] 7. Checkpoint - Ensure all tests pass
  - Run full test suite: `pytest tldr-newsletter/tests/ -v`
  - Ensure bug condition test (Property 1) passes — confirms fix works
  - Ensure preservation tests (Property 2) pass — confirms no regressions
  - Ensure no import errors or runtime exceptions in modified files
  - Verify broken RSS URLs have been removed/replaced (manual review of RSS_FEEDS dict)
  - Ask the user if questions arise


## Task Dependency Graph

```json
{
  "waves": [
    ["1", "2"],
    ["3"],
    ["4"],
    ["5"],
    ["6"],
    ["7"]
  ]
}
```

## Notes

- All property-based tests use the Python `hypothesis` library
- Mock `summarize_article` in all tests to avoid LLM API calls
- Mock `score_relevance` with pre-assigned scores for deterministic test behavior
- The progressive cascade thresholds are: 0.2 → 0.15 → 0.10 → 0.05 → all articles
- MIN_ARTICLES raised from 5 to 8 in both `nlp_pipeline.py` and `pipeline.py`
- Use Python `logging` module (not print statements) for alert and warning logging in new code
