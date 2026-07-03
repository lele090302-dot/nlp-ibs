# Article Delivery Minimum Bugfix Design

## Overview

Subscribers with niche topics consistently receive fewer articles than the guaranteed minimum because (1) broken RSS feed URLs silently yield zero articles, (2) the relevance threshold filter aggressively drops articles with no corrective mechanism to meet the minimum, (3) narrow topic descriptions produce tight embeddings that fail to match legitimately relevant content, and (4) Atom feed date handling and missing entry validation degrade article quality and count. The fix introduces a progressive constraint-relaxation cascade — lowering thresholds, widening freshness, and relaxing dedup scope — to guarantee delivery of at least 8 articles per newsletter, while repairing the upstream feed and scoring issues that cause the shortfall.

## Glossary

- **Bug_Condition (C)**: The condition where the final article count delivered to a subscriber falls below MIN_ARTICLES (8) after all filtering, scoring, dedup, and selection steps
- **Property (P)**: The desired behavior — the system delivers at least MIN_ARTICLES (8) articles per newsletter, or exhausts all fallback strategies and logs an alert
- **Preservation**: Existing behaviors that must remain unchanged: MAX_ARTICLES cap, quality filtering when pool is sufficient, cross-edition dedup under normal conditions, admin-curated priority, balanced topic distribution
- **`fetch_from_rss()`**: Function in `fetcher.py` that parses RSS/Atom feeds per topic; currently uses broken URLs and lacks bozo checking, timeout, and entry validation
- **`process_articles()`**: Function in `nlp_pipeline.py` that scores, filters, selects, and summarizes articles; currently drops below-threshold articles without corrective action
- **`RELEVANCE_THRESHOLD`**: Cosine similarity cutoff (currently 0.2) below which articles are discarded
- **`MIN_ARTICLES`**: Minimum articles guaranteed per newsletter (currently 5, to be raised to 8)
- **Progressive Cascade**: Ordered relaxation of constraints (threshold → freshness → dedup) until minimum is met

## Bug Details

### Bug Condition

The bug manifests when a subscriber's newsletter is assembled and the final article count after all filtering steps is less than MIN_ARTICLES. Multiple compounding factors contribute: broken RSS feeds reduce the source pool, narrow topic descriptions inflate false negatives during scoring, the threshold filter drops articles without fallback enforcement, and Atom-feed date mishandling penalizes fresh articles.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type {subscriber: User, raw_articles: List[Article], pipeline_config: Config}
  OUTPUT: boolean

  articles := fetch_articles_for_topics(subscriber.topics, config.freshness_days)
  articles := deduplicate(articles)
  articles := remove_previously_sent(articles, subscriber.sent_urls)
  scored := score_relevance(articles, subscriber.topics)
  filtered := [a FOR a IN scored WHERE a.relevance_score >= config.RELEVANCE_THRESHOLD]
  selected := balanced_select(filtered, subscriber.topics, config.MAX_ARTICLES)

  RETURN len(selected) < config.MIN_ARTICLES
END FUNCTION
```

### Examples

- **Fintech subscriber**: 4 RSS feeds configured, 2 return HTML (broken), NewsAPI returns 8 articles, after dedup/scoring/threshold only 3 pass → delivers 3 instead of 8
- **Startups subscriber**: Only 2 RSS feeds, narrow topic description "startup ecosystem and venture capital" misses YC demo day articles using different terminology → 4 articles pass threshold
- **GenAI subscriber with history**: Good source pool but cross-edition dedup removes 60% of candidates, remaining 5 pass threshold but below new minimum of 8
- **Multi-topic subscriber (Crypto + Tech)**: Atom feeds use "updated" field, articles get 0.7 decay penalty, drop below threshold → 2 articles delivered
- **Edge case**: All feeds broken AND NewsAPI key expired → 0 articles available, system should log alert and deliver whatever is available (even 0)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Subscribers with abundant relevant articles receive no more than MAX_ARTICLES (10), selected by highest relevance score
- When the article pool is sufficient (≥ MIN_ARTICLES pass threshold), low-relevance articles are still filtered out to maintain quality
- Cross-edition deduplication continues to exclude previously sent articles under normal conditions (only relaxed as last-resort fallback)
- Admin-approved articles take priority over AI-selected articles when approvals exist
- Balanced topic distribution continues to allocate slots fairly across subscriber topics
- Feedback boost continues to elevate preferred sources in ranking

**Scope:**
All pipeline runs where the post-filtering article count already meets or exceeds MIN_ARTICLES (8) should be completely unaffected by this fix. The progressive cascade only activates when count < MIN_ARTICLES.

## Hypothesized Root Cause

Based on the bug description and code analysis, the root causes are:

1. **Broken RSS Feed URLs**: Several entries in `RSS_FEEDS` dict point to HTML pages rather than RSS/Atom XML feeds (e.g., `https://arstechnica.com/ai/`, `https://www.bloomberg.com/ai`, `https://fintechmagazine.com/fintech`). `feedparser.parse()` silently returns zero entries for these, reducing the source pool by ~40-50%.

2. **No Bozo Flag Checking**: When `feedparser` detects a malformed feed, it sets `feed.bozo = 1` but the code never inspects this flag, making broken feeds indistinguishable from empty feeds.

3. **No Timeout on RSS Fetches**: `feedparser.parse(url)` uses no timeout, unlike the NewsAPI call which uses `timeout=10`. A slow server can stall the pipeline.

4. **Missing Entry Validation in RSS**: Unlike `fetch_from_newsapi` which filters `if a.get("title") and a.get("url")`, `fetch_from_rss` appends entries without validating title/link presence.

5. **Atom Date Field Handling**: RSS parser only checks `entry.get("published", "")` and ignores the `"updated"` field used by Atom feeds, causing `_recency_decay` to apply a 0.7 penalty to articles with perfectly valid dates.

6. **Narrow Topic Descriptions**: `TOPIC_DESCRIPTIONS` in `nlp_pipeline.py` use concise phrases that produce tight embeddings. Articles using different terminology (e.g., "Series A" article not matching "venture capital" embedding closely enough) get scored below threshold.

7. **No Minimum Enforcement After Filtering**: `process_articles()` prints a warning when `len(top_articles) < min_articles` but takes no corrective action. The single fallback (lowering threshold to 0.1) only triggers when zero articles pass, not when count is merely below minimum.

8. **Freshness Widening at Wrong Stage**: `pipeline.py` checks `len(raw_articles) < MIN_ARTICLES` before scoring/filtering. After scoring removes 60-70% of articles, the count drops below minimum but no further widening occurs.

## Correctness Properties

Property 1: Bug Condition - Minimum Article Delivery Guarantee

_For any_ pipeline execution where the initial filtering produces fewer than MIN_ARTICLES (8) articles for a subscriber, the fixed system SHALL activate the progressive constraint-relaxation cascade (lower threshold → widen freshness → relax dedup) and deliver at least MIN_ARTICLES articles, OR exhaust all fallback strategies and log an explicit alert while delivering all available articles.

**Validates: Requirements 2.2, 2.3, 2.4, 2.6**

Property 2: Preservation - Sufficient Pool Behavior Unchanged

_For any_ pipeline execution where the initial filtering produces MIN_ARTICLES (8) or more articles for a subscriber, the fixed system SHALL produce the same selection result as the original system — capping at MAX_ARTICLES (10), applying quality filtering, cross-edition dedup, balanced distribution, and feedback boost identically to the unfixed code.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `fetcher.py`

**Function**: `fetch_from_rss()`

**Specific Changes**:
1. **Replace broken RSS URLs**: Remove HTML page URLs and replace with valid RSS/Atom feed equivalents:
   - `https://arstechnica.com/ai/` → `https://arstechnica.com/ai/feed/` (or remove)
   - `https://www.bloomberg.com/ai` → remove (no public RSS available)
   - `https://www.bloomberg.com/technology` → remove (no public RSS available)
   - `https://www.bloomberg.com/technology/startups` → remove
   - `https://www.wsj.com/tech/ai` → remove (paywalled, no public RSS)
   - `https://fintechmagazine.com/fintech` → remove (no valid RSS)
   - `https://fintechmagazine.com/crypto` → remove (no valid RSS)
   - `https://arstechnica.com/gadgets/` → `https://arstechnica.com/gadgets/feed/`

2. **Add bozo flag checking**: After `feedparser.parse()`, check `feed.bozo` and log a warning if set with zero entries, then skip that feed.

3. **Use requests.get with timeout**: Replace direct `feedparser.parse(url)` with `requests.get(url, timeout=10)` followed by `feedparser.parse(response.content)` to enforce timeout.

4. **Add entry validation**: Only append entries where `entry.get("title")` and `entry.get("link")` are non-empty, matching `fetch_from_newsapi` behavior.

5. **Fix date field fallback**: Change `entry.get("published", "")` to `entry.get("published") or entry.get("updated", "")` to support Atom feeds.

---

**File**: `nlp_pipeline.py`

**Function**: `process_articles()` and module-level constants

**Specific Changes**:
1. **Broaden TOPIC_DESCRIPTIONS**: Expand each topic description with named entities, subcategories, and varied terminology to produce wider embeddings that capture more legitimately relevant articles.

2. **Implement progressive threshold cascade**: After the initial threshold filter, if `len(filtered) < min_articles`, progressively lower the threshold through steps [0.15, 0.10, 0.05] re-filtering the scored list at each level until minimum is met.

3. **Post-filter freshness widening**: If the cascade exhausts threshold levels and count is still below minimum, signal the caller to widen freshness days and re-fetch/re-score.

4. **Update MIN_ARTICLES default parameter**: Change default `min_articles` parameter from 5 to 8.

---

**File**: `pipeline.py`

**Function**: `stage_pipeline()` and `send_pipeline()`

**Specific Changes**:
1. **Raise MIN_ARTICLES constant**: Change from 5 to 8.

2. **Move freshness check after filtering**: Re-evaluate article count after scoring and threshold filtering, not just after raw fetch. If post-filter count < MIN_ARTICLES, widen freshness and re-run the scoring pipeline.

3. **Implement constraint relaxation priority**: (1) lower threshold, (2) widen freshness, (3) relax dedup scope — each tried in sequence until minimum met.

4. **Add alert logging**: When minimum cannot be met after all fallbacks exhausted, log an explicit alert with details of which strategies were attempted and the final shortfall.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that mock RSS feed responses (returning HTML for broken URLs) and NewsAPI responses (limited results), then run the full pipeline for niche-topic subscribers and assert article count. Run these tests on the UNFIXED code to observe failures confirming the minimum is not met.

**Test Cases**:
1. **Broken RSS Feed Test**: Mock `feedparser.parse()` with a feed where `bozo=1` and zero entries — verify the system silently produces zero articles from that feed (will confirm root cause on unfixed code)
2. **Threshold Drops Below Minimum Test**: Provide 12 articles where only 4 score above 0.2 — verify system delivers only 4 (will fail minimum on unfixed code)
3. **Atom Date Penalty Test**: Provide articles with only "updated" field set — verify they get 0.7 penalty and drop below threshold (will confirm date handling root cause)
4. **Compounding Factors Test**: Combine broken feeds + narrow descriptions + dedup for a niche subscriber — verify delivered count is well below 8 (will fail on unfixed code)

**Expected Counterexamples**:
- `process_articles()` returns fewer than 8 articles for niche subscribers
- Broken RSS feeds contribute 0 articles with no warning logged
- Atom-feed articles receive incorrect recency penalty

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := process_articles_fixed(input.articles, input.topics, min_articles=8)
  ASSERT len(result) >= 8 OR (all_fallbacks_exhausted AND alert_logged)
  ASSERT all articles in result have non-empty title AND non-empty url
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT process_articles_original(input) == process_articles_fixed(input)
  // When pool is sufficient, cascade never activates, results identical
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many article sets with varying scores, topics, and counts to verify the cascade never activates when the pool is already sufficient
- It catches edge cases around the MIN_ARTICLES boundary (exactly 8, 9, 10 articles passing threshold)
- It provides strong guarantees that quality filtering and MAX_ARTICLES cap remain intact

**Test Plan**: Observe behavior on UNFIXED code first for subscribers with abundant articles (≥8 passing threshold), then write property-based tests capturing that behavior remains identical after the fix.

**Test Cases**:
1. **MAX_ARTICLES Cap Preservation**: Generate article sets where 15+ articles pass threshold — verify exactly MAX_ARTICLES (10) are returned, same selection as original
2. **Quality Filter Preservation**: Generate article sets with mix of high/low scores where ≥8 pass threshold — verify low-scoring articles are still excluded
3. **Balanced Distribution Preservation**: Generate multi-topic article sets with sufficient pool — verify topic slot allocation is identical
4. **Dedup Preservation**: Generate article sets with previously-sent URLs where remaining pool ≥8 — verify dedup still excludes sent articles

### Unit Tests

- Test `fetch_from_rss` with mocked broken feed (bozo=1) — verify warning logged and feed skipped
- Test `fetch_from_rss` with mocked valid Atom feed using "updated" field — verify date is captured
- Test `fetch_from_rss` with timeout simulation — verify 10-second timeout enforced
- Test `fetch_from_rss` entry validation — verify entries without title/link are excluded
- Test progressive threshold cascade with 6 articles at various score levels — verify cascade lowers until 8 met
- Test cascade terminates when minimum met (doesn't over-relax)
- Test alert logging when all fallbacks exhausted

### Property-Based Tests

- Generate random article sets with varying relevance scores and verify: if ≥8 pass initial threshold, output matches original behavior exactly (preservation)
- Generate random article sets where <8 pass initial threshold and verify: cascade activates and delivers ≥8 OR logs alert (fix validation)
- Generate random RSS feed responses and verify: broken feeds are detected and skipped, valid feeds produce articles with non-empty title/url/date
- Generate random topic combinations and verify: balanced distribution algorithm produces same allocation when pool is sufficient

### Integration Tests

- End-to-end pipeline test with mocked external APIs: verify niche-topic subscriber receives ≥8 articles after fix
- End-to-end pipeline test with abundant articles: verify behavior unchanged from original
- Test constraint relaxation priority order: verify threshold lowered first, then freshness widened, then dedup relaxed
- Test alert pathway: verify explicit log message when all strategies exhausted
