# Implementation Plan: Rephrased Article Titles

## Overview

Add a title-rephrasing step to `nlp_pipeline.py` that rewrites each selected article's headline using the Groq LLM client, with robust fallback behavior and a hard 100-character limit. The rephraser integrates into the existing per-article enrichment loop after summarization and before reading-time estimation. No changes to `fetcher.py` deduplication or `newsletter.html` template rendering are needed.

## Tasks

- [x] 1. Implement helper functions for title rephrasing
  - [x] 1.1 Implement `_clean_title_fallback()` in `nlp_pipeline.py`
    - Add function that strips HTML tags (via BeautifulSoup) and markdown formatting (bold, italic, headers, inline code, blockquotes, horizontal rules, links) from a title string
    - Return plain text result with no truncation or rewording
    - Follow the same markdown-stripping pattern already used in `_clean_summary()`
    - _Requirements: 3.1, 3.2_

  - [x] 1.2 Implement `_truncate_at_word_boundary()` in `nlp_pipeline.py`
    - Add function that truncates text to `max_len` (default 100) at the nearest preceding word boundary
    - If text is already ≤ max_len, return unchanged
    - If no space found before max_len (single long word), truncate at max_len directly
    - Strip trailing whitespace from result
    - _Requirements: 2.5_

  - [x] 1.3 Implement `_is_unchanged_title()` in `nlp_pipeline.py`
    - Add function that compares original and rephrased titles after case-insensitive, whitespace-normalized comparison
    - Normalize both: lowercase, collapse multiple whitespace to single space, strip leading/trailing whitespace
    - Return True if normalized forms are equal
    - _Requirements: 1.6_

- [x] 2. Implement the main rephrasing function and integration
  - [x] 2.1 Add `REPHRASE_TITLE_PROMPT` constant to `nlp_pipeline.py`
    - Define the prompt template instructing the LLM to rewrite headlines
    - Include rules: max 100 characters, crisp/catchy/engaging for academic audience, no clickbait/sensationalized language/ALL CAPS/tabloid style, no jargon/abbreviations, preserve factual meaning/named entities/numbers/core claim
    - Use `{title}` placeholder for the original headline
    - Output instruction: "Output ONLY the rewritten headline, nothing else"
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 2.2 Implement `rephrase_title()` function in `nlp_pipeline.py`
    - Store `article['title']` into `article['original_title']` (byte-for-byte)
    - Call `get_groq_client().chat.completions.create()` with REPHRASE_TITLE_PROMPT, model `llama-3.1-8b-instant`, max_tokens=60, temperature=0.7
    - Validate response: non-empty after strip, not whitespace-only, not identical to original (via `_is_unchanged_title()`)
    - If valid: apply `_truncate_at_word_boundary(response, 100)`, store in `article['title']`
    - If invalid or exception: log warning, apply `_clean_title_fallback(original)`, store in `article['title']`
    - Return the mutated article dict
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6, 3.1, 3.4_

  - [x] 2.3 Integrate `rephrase_title()` into `process_articles()` enrichment loop
    - In the per-article loop, after `summarize_article()` completes and before `estimate_reading_time()`
    - Build article dict with summary, then pass to `rephrase_title()`
    - Use the returned dict (with `title`, `original_title` fields) for the rest of enrichment
    - Ensure pipeline continues processing remaining articles even if rephrasing fails for one
    - _Requirements: 1.4, 3.3, 4.1_

- [x] 2.4 Fix reading time estimation to use full article content
    - Currently `estimate_reading_time()` is called with `article.get("content") or article.get("description") or ""` which is typically a short snippet (~200 chars from NewsAPI, or RSS summary), resulting in 1 min for every article
    - Add a helper `_fetch_full_article_text(url: str) -> str` in `nlp_pipeline.py` that fetches the article URL with `requests.get(url, timeout=8)`, extracts body text with `BeautifulSoup(html, "html.parser").get_text(separator=" ")`, and returns the extracted text
    - Wrap the fetch in try/except: on any exception (timeout, connection error, HTTP error, parse error), return an empty string
    - In the `process_articles()` enrichment loop, call `_fetch_full_article_text(article['url'])` to get the full text
    - Pass the full text to `estimate_reading_time()` if non-empty; if empty (fetch failed), use a fallback of 4 minutes
    - Replace the current logic: `reading_time = estimate_reading_time(article.get("content") or article.get("description") or "")` with the new fetch-based approach
    - No new dependencies needed (requests + BeautifulSoup already imported)

- [x] 3. Checkpoint - Verify core implementation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Write property-based and unit tests
  - [x] 4.1 Write property test for title field assignment (Property 1)
    - **Property 1: Title field assignment after rephrasing**
    - For any article with non-empty title and any valid LLM response, after `rephrase_title()` completes, `article['title']` holds the (possibly truncated) rephrased value AND `article['original_title']` holds the byte-for-byte original
    - Mock Groq client to return controlled responses
    - Use `@settings(max_examples=100, deadline=None)`
    - **Validates: Requirements 1.2, 1.3, 4.1**

  - [x] 4.2 Write property test for fallback on invalid LLM response (Property 2)
    - **Property 2: Fallback on invalid LLM response**
    - For any article with non-empty title, if LLM response is empty, whitespace-only, or identical to original after normalization, `rephrase_title()` sets `article['title']` to the cleaned original and does not retry
    - Mock Groq client to return empty/whitespace/identical responses
    - Use `@settings(max_examples=100, deadline=None)`
    - **Validates: Requirements 1.5, 1.6, 3.1**

  - [x] 4.3 Write property test for word-boundary truncation (Property 3)
    - **Property 3: Word-boundary truncation enforces 100-character limit**
    - For any string > 100 chars, `_truncate_at_word_boundary(text, 100)` returns a string ≤ 100 chars ending at a word boundary; for any string ≤ 100 chars, returns unchanged
    - Use Hypothesis `st.text()` strategy with varying lengths (50–300 chars)
    - Use `@settings(max_examples=100, deadline=None)`
    - **Validates: Requirements 2.5**

  - [x] 4.4 Write property test for HTML/markdown stripping (Property 4)
    - **Property 4: HTML and markdown stripping preserves text content**
    - For any string with HTML tags or markdown, `_clean_title_fallback()` returns a string with no HTML tags and no markdown syntax characters, and the plain text content is preserved
    - Use Hypothesis strategies to generate strings with injected HTML/markdown
    - Use `@settings(max_examples=100, deadline=None)`
    - **Validates: Requirements 3.2**

  - [x] 4.5 Write property test for pipeline continuity on failure (Property 5)
    - **Property 5: Pipeline continuity on rephrasing failure**
    - For any list of articles where the Groq client raises an exception for every rephrase call, `process_articles()` returns the same number of articles, each with `title`, `original_title`, and `reading_time` fields
    - Mock Groq client to always raise exception for rephrase, return valid summary for summarize
    - Use `@settings(max_examples=100, deadline=None)`
    - **Validates: Requirements 3.3, 3.4**

  - [x] 4.6 Write unit tests for prompt content and integration ordering
    - Test that `REPHRASE_TITLE_PROMPT` contains instructions for 100-char limit, anti-clickbait, no jargon, and factual preservation
    - Test that `rephrase_title()` is called after `summarize_article()` in the enrichment loop (verify call order via mocks)
    - Test that fetcher deduplication is unaffected (operates on raw title before rephrasing)
    - Test that newsletter template renders `{{ article.title }}` (already does, just verify field is used)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 1.4, 4.2, 5.1_

- [x] 5. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and integration ordering
- All tests go in `tldr-newsletter/tests/test_rephrase_title.py`
- Mock the Groq client and sentence-transformers to avoid real API calls and ML model loading (matching existing test patterns in the project)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["2.3", "2.4"] },
    { "id": 4, "tasks": ["4.1", "4.2", "4.3", "4.4"] },
    { "id": 5, "tasks": ["4.5", "4.6"] }
  ]
}
```
