# Spam Source Blocklist Design

## Overview

The TL;DR Newsletter fetcher currently accepts articles from all sources returned by NewsAPI, allowing spam sources like Biztoc.com to degrade newsletter quality. This design formalizes the source blocklist mechanism and its integration into the fetch pipeline.

The fix implements a three-part solution: (1) a maintainable blocklist stored in a YAML configuration file, (2) efficient loading and validation on startup, and (3) filtering at the point of fetch completion in `fetch_from_newsapi()`. This approach ensures spam sources are blocked early in the pipeline, preventing wasteful processing and admin review time.

## Glossary

- **Bug_Condition (C)**: An article source exists in the NewsAPI response AND that source is on the spam blocklist
- **Property (P)**: Articles matching the bug condition are filtered out and never returned from `fetch_from_newsapi()`
- **Preservation**: All articles from non-blocked sources continue to be processed and returned exactly as before; RSS feeds continue unchanged; deduplication logic remains unaffected
- **fetch_from_newsapi()**: Function in `tldr-newsletter/fetcher.py` that queries NewsAPI and returns article metadata (title, URL, source, etc.)
- **blocklist**: A set of source names (e.g., "Biztoc", "YahooFinance") that should be excluded from pipeline processing
- **source**: The `source.name` field returned by NewsAPI for each article, representing the publication name

## Bug Details

### Bug Condition

The bug manifests when NewsAPI returns articles from spam sources (e.g., "Biztoc") that redirect to unreliable websites. The `fetch_from_newsapi()` function accepts these articles without validation, allowing them to propagate through the review queue and into subscriber newsletters.

**Formal Specification:**
```
FUNCTION isBugCondition(article)
  INPUT: article of type dict (NewsAPI response article)
  OUTPUT: boolean
  
  source_name := article["source"]["name"]
  RETURN source_name IN SPAM_BLOCKLIST
END FUNCTION
```

### Examples

**Example 1: Biztoc Article (Buggy Input)**
- Input: `{"title": "Bitcoin Soars 25%", "source": {"name": "Biztoc"}, "url": "https://...", ...}`
- Current behavior: Article accepted and returned from `fetch_from_newsapi()`
- Expected behavior: Article filtered out; not included in function output
- Bug manifestation: Spam article reaches review queue; admin must review and reject

**Example 2: TechCrunch Article (Non-Buggy Input)**
- Input: `{"title": "OpenAI Launches GPT-5", "source": {"name": "TechCrunch"}, "url": "https://techcrunch.com/...", ...}`
- Current behavior: Article accepted and returned
- Expected behavior: Article accepted and returned (no change)
- Preservation: TechCrunch articles remain unaffected

**Example 3: Yahoo Finance Article (Buggy Input)**
- Input: `{"title": "Fed Rate Decision", "source": {"name": "Yahoo Finance"}, "url": "https://...", ...}`
- Current behavior: Article accepted (may or may not be spam depending on user tolerance)
- Expected behavior: Filtered if "Yahoo Finance" is in blocklist; passed through if not
- Edge case: Blocklist configuration determines behavior

**Example 4: RSS Feed Article from Curated Source (Non-Buggy Input)**
- Input: RSS feed article from "Hacker News"
- Current behavior: Processed via `fetch_from_rss()`; no source-based filtering
- Expected behavior: Unchanged; RSS sources assumed trustworthy and bypass blocklist
- Preservation: RSS articles unaffected by fix

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Legitimate sources (TechCrunch, VentureBeat, Ars Technica, The Verge, etc.) continue to be accepted and returned from `fetch_from_newsapi()`
- RSS feeds continue to be fetched and processed by `fetch_from_rss()` without source filtering
- Deduplication by URL and near-duplicate title normalization remains unaffected
- Article metadata (title, description, content, published_at) is passed through unchanged for non-blocked sources
- NewsAPI pagination and sorting remain unchanged

**Scope:**
All articles from sources NOT in the blocklist are completely unaffected by this fix. The blocklist is exclusionary only:
- Articles from legitimate sources are returned as before
- No performance impact for non-blocked sources
- No changes to API parameter handling or response parsing
- No changes to error handling for API failures

## Hypothesized Root Cause

The current implementation lacks any source validation layer. The root causes are:

1. **Missing Validation Layer**: `fetch_from_newsapi()` returns all articles without checking source credibility. The function directly converts API response articles to internal format without filtering.

2. **No Blocklist Configuration**: No centralized list exists defining spam sources. Decisions to include/exclude sources are made implicitly (all sources accepted by default).

3. **Manual Admin Burden**: Without automatic filtering, admins must manually review spam articles in the queue and reject them. This scales poorly as the blocklist grows.

4. **No Extensibility Mechanism**: Adding new spam sources requires either code changes or a hidden configuration. There's no user-friendly way to update the blocklist without engineering involvement.

5. **Pipeline Inefficiency**: Spam articles consume resources (database space, admin review time, query bandwidth) throughout their lifecycle. Early filtering is more efficient than late rejection.

## Correctness Properties

Property 1: Bug Condition - Spam Source Filtering

_For any_ article where the bug condition holds (source is in the blocklist), the fixed `fetch_from_newsapi()` function SHALL NOT include that article in the returned list. The article is discarded during processing and never reaches downstream systems.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation - Non-Blocked Source Pass-Through

_For any_ article where the bug condition does NOT hold (source is NOT in the blocklist), the fixed `fetch_from_newsapi()` function SHALL return the article with identical metadata (title, URL, source, description, content, topic, published_at) as the original unfixed function, preserving all legitimate source processing.

**Validates: Requirements 3.1, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct, the fix involves:

**File 1: `tldr-newsletter/fetcher.py`**

**Function: `fetch_from_newsapi()`**

**Specific Changes:**

1. **Add Blocklist Loading Function**
   - Create a new function `load_spam_blocklist()` that reads the blocklist YAML file and returns a set of source names for O(1) lookup
   - Load on module initialization to avoid file I/O on every fetch call
   - Cache the blocklist in a module-level variable (`_SPAM_BLOCKLIST`)

2. **Add Blocklist Path Configuration**
   - Define a module constant `BLOCKLIST_PATH = "config/spam_sources.yaml"` at the top of `fetcher.py`
   - Allow override via environment variable `SPAM_BLOCKLIST_PATH` for deployment flexibility

3. **Add Source Validation After API Response**
   - After parsing the NewsAPI JSON response and before converting articles to internal format
   - For each article, extract `source_name = a.get("source", {}).get("name", "Unknown")`
   - Check `if source_name.lower() in _SPAM_BLOCKLIST` before including in results list
   - Log filtered articles at DEBUG level for audit trail: `logger.debug(f"[NewsAPI] Filtered spam source: {source_name}")`

4. **Add Blocklist Reload Capability**
   - Create a function `reload_blocklist()` that can be called to refresh the blocklist at runtime
   - Useful for configuration updates without restarting the service

5. **Add Error Handling for Missing Blocklist**
   - If blocklist file not found or unreadable, log a WARNING and proceed with empty blocklist (fail-open)
   - This prevents the fetcher from crashing if config is unavailable

**File 2: `config/spam_sources.yaml`** (new file)

**Structure:**
```yaml
# Spam Sources Blocklist
# Sources listed here are excluded from the NewsAPI fetch pipeline
# Update this file to add new spam sources; changes take effect on next fetcher startup

blocked_sources:
  - Biztoc
  - Yahoo Finance  # Be careful with this one—some users may find value
  - Investor's Business Daily  # frequent low-quality headlines
  # Add more as needed
```

**Characteristics:**
- Human-readable YAML format for easy maintenance
- Case-insensitive source name matching (normalize to lowercase)
- Comments to document reasoning for each blocked source
- Version-controllable (stored in git) for audit trail

**File 3: `tldr-newsletter/.env.example`**

**Addition:**
```
# Spam source blocklist configuration
SPAM_BLOCKLIST_PATH=config/spam_sources.yaml
```

**Update `.env`:** Include the same variable if deploying to production.

### Implementation Pseudocode

```
MODULE fetcher:
  _SPAM_BLOCKLIST = set()  # Module-level cache
  
  FUNCTION load_spam_blocklist():
    GLOBAL _SPAM_BLOCKLIST
    try:
      path := env("SPAM_BLOCKLIST_PATH") or "config/spam_sources.yaml"
      config := yaml.load(read_file(path))
      sources := config.get("blocked_sources", [])
      _SPAM_BLOCKLIST := {s.lower() for s in sources}
      log("Loaded spam blocklist with " + len(_SPAM_BLOCKLIST) + " sources")
    catch FileNotFound:
      log_warning("Blocklist file not found; using empty blocklist")
      _SPAM_BLOCKLIST := {}
    catch ParseError as e:
      log_warning("Failed to parse blocklist YAML: " + str(e))
      _SPAM_BLOCKLIST := {}
    return _SPAM_BLOCKLIST
  
  # Call at module import time
  _SPAM_BLOCKLIST := load_spam_blocklist()
  
  FUNCTION reload_blocklist():
    GLOBAL _SPAM_BLOCKLIST
    _SPAM_BLOCKLIST := load_spam_blocklist()
  
  FUNCTION fetch_from_newsapi(topic, page_size, freshness_days):
    GLOBAL _SPAM_BLOCKLIST
    
    # ... existing query building code ...
    
    articles := []
    FOR EACH a IN resp.json()["articles"]:
      IF a.get("title") AND a.get("url"):
        source_name := a.get("source", {}).get("name", "Unknown")
        
        # NEW: Check if source is blocked
        IF source_name.lower() IN _SPAM_BLOCKLIST:
          log_debug("Filtered spam source: " + source_name)
          continue  # Skip this article
        
        # Existing article processing
        article := {
          "title": a.get("title"),
          "url": a.get("url"),
          "source": source_name,
          "published_at": a.get("publishedAt"),
          "description": a.get("description") or "",
          "content": a.get("content") or "",
          "topic": topic
        }
        articles.append(article)
    
    return articles
```

## Testing Strategy

### Validation Approach

The testing strategy follows a three-phase approach: (1) surface the bug with exploratory tests on unfixed code, (2) verify the fix filters spam sources correctly, and (3) verify legitimate sources continue to work unchanged.

### Exploratory Bug Condition Checking

**Goal**: Demonstrate that spam articles from Biztoc are currently accepted on unfixed code. Confirm the root cause (missing source validation).

**Test Plan**: Mock the NewsAPI response to include Biztoc articles and verify that unfixed `fetch_from_newsapi()` returns them. This establishes the baseline defective behavior.

**Test Cases:**

1. **Biztoc Article Accepted (Unfixed Code)**: Call `fetch_from_newsapi()` with mocked response containing Biztoc article; assert article is returned. This will PASS on unfixed code and demonstrates the bug.

2. **Yahoo Finance Article Accepted (Unfixed Code)**: Call with mocked Yahoo Finance article; assert article is returned. Confirms that all sources currently accepted.

3. **Multiple Spam Sources Mixed (Unfixed Code)**: Mock response with 50% legitimate (TechCrunch), 50% spam (Biztoc, Yahoo Finance); assert all articles returned. Confirms no filtering logic exists.

4. **Edge Case - Empty Source Name (Unfixed Code)**: Mock article with missing/empty source field; verify unfixed function handles gracefully (defaults to "Unknown").

**Expected Counterexamples:**
- Spam articles are included in results on unfixed code
- No filtering logic is present in `fetch_from_newsapi()`
- Source validation is completely absent

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds (source in blocklist), the fixed function filters them out.

**Pseudocode:**
```
FOR ALL article WHERE isBugCondition(article) DO
  result := fetch_from_newsapi_fixed(topic, mocked_response=[article] + others)
  ASSERT article NOT IN result.articles
  ASSERT "Filtered spam source" IN logs
END FOR
```

**Test Implementation:**
- Mock NewsAPI responses with Biztoc, Yahoo Finance, and other spam sources
- Call fixed `fetch_from_newsapi()`
- Assert that spam articles are excluded from returned list
- Assert that log messages indicate filtering action
- Verify result count is reduced appropriately

**Test Cases:**
1. **Biztoc Article Filtered**: Mock with Biztoc; verify filtered out
2. **Yahoo Finance Article Filtered**: Mock with Yahoo Finance; verify filtered out
3. **Multiple Spam Sources Filtered**: Mock response with 10 legitimate + 10 spam; verify only 10 legitimate returned
4. **Blocklist Case Insensitivity**: Mock "BIZTOC" (uppercase); verify still filtered
5. **Blocklist Reload**: Call `reload_blocklist()` and verify filtering still works with reloaded config

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (source NOT in blocklist), the fixed function returns articles identically to the original.

**Pseudocode:**
```
FOR ALL article WHERE NOT isBugCondition(article) DO
  result_original := fetch_from_newsapi_original(topic, mocked_response)
  result_fixed := fetch_from_newsapi_fixed(topic, mocked_response)
  
  FOR EACH returned_article IN result_fixed:
    original_article := find_by_url(result_original, returned_article.url)
    ASSERT returned_article.title == original_article.title
    ASSERT returned_article.url == original_article.url
    ASSERT returned_article.source == original_article.source
    ASSERT returned_article.description == original_article.description
    ASSERT returned_article.content == original_article.content
    ASSERT returned_article.published_at == original_article.published_at
    ASSERT returned_article.topic == original_article.topic
END FOR
```

**Testing Approach**: Property-based testing is recommended because:
- It generates many combinations of legitimate sources across multiple topics
- It catches edge cases in metadata handling (special characters, encoding, length)
- It provides guarantees that legitimate articles are unaffected

**Test Plan:** Use Hypothesis to generate random combinations of legitimate sources (TechCrunch, VentureBeat, Ars Technica, etc.) and article metadata. Verify that fixed function returns identical results to original for non-blocked sources.

**Test Cases:**

1. **TechCrunch Preservation**: Mock response with TechCrunch articles; verify identical returned data
2. **VentureBeat Preservation**: Verify metadata unchanged for VentureBeat articles
3. **Multiple Legitimate Sources**: Mock response with 5+ different non-blocked sources; verify all returned with correct metadata
4. **Metadata Integrity**: Verify special characters, unicode, long titles/descriptions preserved exactly
5. **Empty Article Fields**: Verify handling of empty description/content (should remain empty, not transformed)
6. **RSS Feeds Unaffected**: Verify `fetch_from_rss()` continues to work unchanged
7. **Deduplication Unchanged**: Verify `deduplicate()` function behavior unchanged

### Unit Tests

- Test `load_spam_blocklist()` function correctly parses YAML and returns set
- Test `load_spam_blocklist()` with missing file (should not crash, empty blocklist)
- Test `load_spam_blocklist()` with malformed YAML (should log warning, use empty set)
- Test `reload_blocklist()` updates the cached blocklist
- Test case-insensitive source name matching
- Test filtering logic: spam sources excluded, legitimate sources included
- Test that logging occurs for filtered articles (audit trail)

### Property-Based Tests

- Generate random valid source names and verify correct classification (blocked or not)
- Generate random article metadata and verify non-blocked articles returned unchanged
- Generate random blocklist configurations and verify consistent behavior
- Test combinations of legitimate sources and verify all returned correctly
- Generate edge cases: empty source names, special characters, very long source names

### Integration Tests

- Test full `fetch_articles_for_topics()` pipeline with spam sources present
- Verify spam articles never reach `deduplicate()` function
- Test that blocklist updates take effect across multiple sequential fetch calls
- Test fetching multiple topics simultaneously; verify spam filtering applied per topic
- Test with realistic NewsAPI response structure (multiple sources, paginated results)
- Test that review queue never receives spam articles after fix
- Test end-to-end: article fetching → deduplication → review queue population; verify no spam appears

