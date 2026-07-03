# Implementation Plan

## Overview

Fix four newsletter quality bugs: stale article inclusion (no date filtering), truncated/markdown-polluted summaries, Gmail email clipping (HTML > 102 KB), and cross-edition article duplication. The implementation follows the exploratory bugfix workflow: write tests to confirm bugs exist, write preservation tests to capture baseline behavior, implement fixes, then verify all tests pass.

## Tasks

- [ ] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Newsletter Quality Bugs (Stale Articles, Truncated Summaries, Oversized Email, Duplicate Articles)
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bugs exist
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the four quality bugs exist
  - **Scoped PBT Approach**: Scope properties to concrete failing cases for each bug condition:
    - Freshness: Generate articles with `published_at` older than 3 days, verify they are NOT excluded by `fetch_from_rss()` or `fetch_from_newsapi()` (confirms no date filtering exists)
    - Summary quality: Call `summarize_article()` with complex articles, assert output ends with terminal punctuation (`.`, `!`, `?`) and contains no markdown (`**`, `*`, `#`, `` ` ``). Test will FAIL because `max_tokens=120` causes truncation and no post-processing strips markdown
    - Email size: Build newsletter with 10 articles using `build_html()`, assert `len(html.encode('utf-8')) <= 102_000`. Test will FAIL because 10 fully-styled articles exceed Gmail's clip limit
    - Deduplication: Call `process_articles()` with a set of `sent_urls` containing URLs that also exist in the article pool, assert none of the sent URLs appear in output. Test will FAIL because `process_articles()` does not accept or filter by `sent_urls`
  - Run test on UNFIXED code - expect FAILURE (this confirms the bugs exist)
  - Document counterexamples found (e.g., "fetch_from_rss returns article from 2023", "summary ends with incomplete word", "HTML is 118KB", "duplicate URL in output")
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Relevance Scoring, Topic Distribution, Feedback Boosts, and Summary Pass-Through
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: For fresh articles (< 24 hours old), `score_relevance()` returns cosine similarity scores on unfixed code
  - Observe: `_balanced_select()` distributes articles equally across topics on unfixed code
  - Observe: Feedback boost adjusts scores by source-level offsets on unfixed code
  - Observe: Well-formed summaries (ending in `.`, `!`, `?` with no markdown) pass through `_clean_summary()` unchanged
  - Write property-based tests capturing observed behavior:
    - For all fresh articles (age < 12h), `score_relevance()` produces scores based purely on cosine similarity to user topics
    - For all balanced selections with N topics and K articles, each topic gets approximately K/N articles (±1)
    - For all articles with feedback boost applied, final score = relevance_score + boost (clamped to ±0.15)
    - For all well-formed summary strings (end with terminal punctuation, no markdown), `_clean_summary(text) == text`
  - Verify tests PASS on UNFIXED code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [ ] 3. Implement cross-edition deduplication (db.py)

  - [ ] 3.1 Add `sent_articles` table to `init_db()`
    - Create table with columns: id, email, article_url, sent_at, run_id, UNIQUE(email, article_url)
    - Add index on email column for fast lookups
    - _Bug_Condition: isBugCondition(input) where article.url IN edition_history.sent_article_urls_
    - _Expected_Behavior: Previously sent articles excluded from candidate selection_
    - _Preservation: Existing tables and functions unchanged_
    - _Requirements: 2.7, 3.7_

  - [ ] 3.2 Add `log_sent_articles(email, article_urls, run_id)` function
    - Bulk insert sent article URLs with timestamp and run_id
    - Use INSERT OR IGNORE to handle UNIQUE constraint gracefully
    - _Requirements: 2.7_

  - [ ] 3.3 Add `get_sent_article_urls(email) -> set[str]` function
    - Query all previously sent article URLs for a given user
    - Return as a set for O(1) lookup during filtering
    - _Requirements: 2.7_

  - [ ] 3.4 Add `clean_old_sent_articles(days=90)` function
    - Delete entries older than 90 days to prevent unbounded DB growth
    - _Requirements: 2.7_

- [ ] 4. Implement freshness filtering (fetcher.py)

  - [ ] 4.1 Add `freshness_days` parameter to `fetch_from_newsapi()`
    - Add `freshness_days: int = 3` parameter
    - Compute `from_date` as ISO string for N days ago
    - Pass `"from": from_date` in the NewsAPI params dict
    - _Bug_Condition: isBugCondition(input) where article.published_at < (NOW - 3 days)_
    - _Expected_Behavior: NewsAPI only returns articles within freshness window_
    - _Preservation: Articles within freshness window still returned normally_
    - _Requirements: 2.1_

  - [ ] 4.2 Add date parsing and freshness filtering to `fetch_from_rss()`
    - Add `freshness_days: int = 3` parameter
    - Compute cutoff date from `freshness_days`
    - Parse `published_at` using `dateutil.parser.parse()`
    - Skip entries older than cutoff; include entries with unparseable dates (benefit of the doubt)
    - _Bug_Condition: isBugCondition(input) where RSS article.published_at < (NOW - 3 days)_
    - _Expected_Behavior: RSS articles older than freshness window are excluded_
    - _Preservation: Fresh articles and articles with missing dates still included_
    - _Requirements: 2.2_

  - [ ] 4.3 Add `freshness_days` parameter to `fetch_articles_for_topics()`
    - Accept `freshness_days: int = 3` parameter
    - Pass through to both `fetch_from_newsapi()` and `fetch_from_rss()`
    - _Requirements: 2.1, 2.2_

- [ ] 5. Implement summary quality improvements (nlp_pipeline.py)

  - [ ] 5.1 Add `_recency_decay()` function
    - Implement exponential decay: `0.5 ** (age_hours / half_life_hours)` with `half_life_hours=36.0`
    - Parse `published_at` string using `dateutil.parser.parse()`
    - Return 0.7 for unparseable dates (moderate penalty)
    - Return 1.0 for age ≤ 0 hours
    - _Bug_Condition: isBugCondition(input) where stale article scores same as fresh_
    - _Expected_Behavior: Stale articles get decayed scores (36h → 0.5x, 72h → 0.25x)_
    - _Requirements: 2.3_

  - [ ] 5.2 Update `score_relevance()` to apply recency decay
    - After computing cosine similarity, multiply by `_recency_decay(article.get("published_at", ""))`
    - Store the decayed score as `relevance_score`
    - _Bug_Condition: isBugCondition(input) where score ignores article age_
    - _Expected_Behavior: final_score = cosine_similarity × recency_decay_
    - _Preservation: Fresh articles (< 12h) get decay ≈ 0.8–1.0, minimal impact on ranking_
    - _Requirements: 2.3, 3.1_

  - [ ] 5.3 Increase `max_tokens` from 120 to 250 in `summarize_article()`
    - Change `max_tokens=120` to `max_tokens=250`
    - This gives the LLM enough budget for 2–4 complete sentences
    - _Bug_Condition: isBugCondition(input) where summary truncated mid-sentence at 120 tokens_
    - _Expected_Behavior: Summary has sufficient token budget for complete sentences_
    - _Requirements: 2.4_

  - [ ] 5.4 Add `_clean_summary(text)` post-processing function
    - Strip markdown: `**bold**` → `bold`, `*italic*` → `italic`, `# Header` → `Header`, `` `code` `` → `code`, `> blockquote` → text, `---` → removed, `[text](url)` → `text`
    - Trim trailing incomplete sentence: if text doesn't end with `.`, `!`, or `?`, find last sentence boundary and truncate there
    - Strip leading/trailing whitespace
    - _Bug_Condition: isBugCondition(input) where summary contains markdown or ends mid-sentence_
    - _Expected_Behavior: Output always ends on complete sentence, no markdown characters_
    - _Preservation: Well-formed summaries pass through unchanged_
    - _Requirements: 2.4, 2.5, 3.2_

  - [ ] 5.5 Apply `_clean_summary()` in `summarize_article()` before returning
    - Wrap the LLM response and fallback path with `_clean_summary()`
    - _Requirements: 2.4, 2.5_

  - [ ] 5.6 Update `process_articles()` to accept `sent_urls` parameter and use `min_articles=5`
    - Add `sent_urls: set[str] | None = None` parameter
    - Filter out previously sent articles early: `articles = [a for a in articles if a.get("url") not in sent_urls]`
    - Change default `min_articles` from 8 to 5
    - Remove aggressive threshold lowering to 0.05; accept fewer articles instead
    - _Bug_Condition: isBugCondition(input) where duplicates not filtered and min forced to 8_
    - _Expected_Behavior: Sent URLs excluded; minimum articles reduced to 5_
    - _Preservation: Relevance scoring, balanced selection, feedback boosts unchanged_
    - _Requirements: 2.6, 2.7, 3.1, 3.4, 3.6_

- [ ] 6. Implement email size compliance (newsletter_builder.py)

  - [ ] 6.1 Add size guard to `build_html()`
    - Add `max_bytes: int = 95000` parameter
    - After initial render, check `len(html.encode('utf-8'))`
    - If exceeds `max_bytes`, drop last article (lowest-ranked) and re-render
    - Repeat until under limit or at 5 articles minimum
    - _Bug_Condition: isBugCondition(input) where rendered HTML > 102,000 bytes_
    - _Expected_Behavior: HTML always ≤ 95,000 bytes (headroom below Gmail's 102KB clip)_
    - _Preservation: Articles still render with full title, metadata, summary, source link, feedback buttons_
    - _Requirements: 2.6, 3.3_

- [ ] 7. Integrate changes in pipeline orchestrator (pipeline.py)

  - [ ] 7.1 Update `MIN_ARTICLES` constant from 8 to 5
    - _Requirements: 2.6_

  - [ ] 7.2 Pass `freshness_days` to `fetch_articles_for_topics()` calls
    - Use 3-day default in both `stage_pipeline()` and `send_pipeline()`
    - _Requirements: 2.1, 2.2_

  - [ ] 7.3 Add freshness fallback logic
    - If 3-day window yields fewer than `min_articles` quality candidates, retry with `freshness_days=5`
    - _Bug_Condition: isBugCondition(input) where insufficient fresh articles available_
    - _Expected_Behavior: System widens to 5-day window before accepting fewer articles_
    - _Requirements: 2.6_

  - [ ] 7.4 Pass `sent_urls` to `process_articles()` in `send_pipeline()`
    - Query `get_sent_article_urls(user["email"])` before processing each user
    - Pass the set to `process_articles()`
    - _Requirements: 2.7_

  - [ ] 7.5 Log sent articles after successful email delivery
    - After successful send, call `log_sent_articles(user["email"], article_urls, run_id)`
    - _Requirements: 2.7_

- [ ] 8. Verify bug condition exploration test now passes

  - [ ] 8.1 Re-run bug condition exploration test
    - **Property 1: Expected Behavior** - Newsletter Quality Bugs Fixed
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior for all four bug conditions
    - Freshness: `fetch_from_rss()` and `fetch_from_newsapi()` now exclude stale articles
    - Summary: `summarize_article()` returns complete sentences without markdown
    - Size: `build_html()` output stays under 102,000 bytes
    - Dedup: `process_articles()` with `sent_urls` excludes previously sent articles
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms all four bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [ ] 8.2 Verify preservation tests still pass
    - **Property 2: Preservation** - Relevance Scoring, Topic Distribution, Feedback Boosts Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm: fresh article scoring unchanged, topic distribution balanced, feedback boosts applied, well-formed summaries pass through
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [ ] 9. Checkpoint - Ensure all tests pass
  - Run full test suite including unit tests, property-based tests, and integration tests
  - Verify no regressions in existing functionality
  - Confirm all four bug conditions are resolved:
    - No stale articles (> 3 days) in newsletter output
    - All summaries end on complete sentences with no markdown
    - HTML email size ≤ 102 KB
    - No duplicate articles across editions
  - Ensure all tests pass, ask the user if questions arise.

## Task Dependency Graph

```json
{
  "waves": [
    ["1", "2"],
    ["3", "4", "5", "6"],
    ["7"],
    ["8"],
    ["9"]
  ]
}
```

Tasks 1 and 2 are written BEFORE any implementation (tasks 3–7).
Tasks 3, 4, 5, 6 can be implemented in parallel (no interdependencies).
Task 7 integrates all changes and depends on 3, 4, 5, and 6 being complete.
Task 8 verifies tests pass after all implementation is done.
Task 9 is the final checkpoint.

## Notes

- All property-based tests use `hypothesis` (Python) for generation
- The exploration test (task 1) is expected to FAIL on unfixed code — this is correct behavior confirming the bugs exist
- The preservation test (task 2) is expected to PASS on unfixed code — this captures baseline behavior to protect
- After implementation (tasks 3–7), the exploration test should PASS and preservation tests should still PASS
- The `dateutil` package (`python-dateutil`) must be added to `requirements.txt` for date parsing
- The freshness fallback (3-day → 5-day) ensures newsletters always have enough content even during low-activity periods
- The size guard uses 95,000 bytes (not 102,000) to leave headroom for email client wrappers
