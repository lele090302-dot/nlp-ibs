# Newsletter Quality Bugs — Bugfix Design

## Overview

The TL;DR Newsletter pipeline has four quality bugs that degrade reader experience: stale articles (no date filtering), truncated/markdown-polluted summaries, Gmail clipping (HTML exceeds 102 KB), and cross-edition article duplication. The fix strategy adds freshness filtering at the fetch layer, improves summary generation and post-processing, makes article count flexible (5–10) to stay under Gmail's size limit, and introduces a `sent_articles` table for cross-edition deduplication. All changes are scoped to preserve existing relevance scoring, balanced topic distribution, feedback boosts, and admin review workflows.

## Glossary

- **Bug_Condition (C)**: Any input condition that triggers one of the four quality bugs — stale articles entering the pipeline, summaries truncated mid-sentence or containing markdown, email exceeding 102 KB, or duplicate articles across editions
- **Property (P)**: The desired behavior — only fresh articles included, summaries are complete plain-text sentences, email stays under 102 KB, no article repeats across editions
- **Preservation**: Existing behaviors that must remain unchanged — relevance scoring, balanced topic distribution, feedback boosts, admin review/approval flow, rendering of article cards
- **`fetch_from_newsapi()`**: Function in `fetcher.py` that queries NewsAPI; currently has no `from` date parameter
- **`fetch_from_rss()`**: Function in `fetcher.py` that parses RSS feeds; currently does no date filtering
- **`score_relevance()`**: Function in `nlp_pipeline.py` that ranks articles by cosine similarity to user topics
- **`summarize_article()`**: Function in `nlp_pipeline.py` that calls Groq LLM with `max_tokens=120`
- **`process_articles()`**: Orchestrator in `nlp_pipeline.py` that scores, filters, selects, and summarizes articles
- **`build_html()`**: Function in `newsletter_builder.py` that renders the Jinja2 template
- **Recency decay**: A multiplicative penalty applied to relevance scores based on article age
- **Freshness window**: The time range (default 3 days, fallback 5 days) within which articles are considered candidates

## Bug Details

### Bug Condition

The bug manifests when any of these conditions hold:

1. An article older than 3 days enters the pipeline because neither `fetch_from_newsapi()` nor `fetch_from_rss()` filters by date
2. The LLM summary is truncated mid-sentence because `max_tokens=120` is too low, or contains markdown formatting (`**`, `*`, `#`, backticks) that was not stripped
3. The rendered HTML email exceeds ~102 KB (Gmail's clip threshold) because the system always targets 8–10 articles regardless of total size
4. An article that was already sent in a previous edition is included again because there is no cross-edition deduplication

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type PipelineRun (articles, user, edition_history)
  OUTPUT: boolean

  stale := ANY article IN input.articles WHERE
           article.published_at < (NOW - 3 days)
           AND article IS included in final newsletter

  truncated := ANY article IN input.articles WHERE
               article.summary ends mid-sentence (no terminal punctuation)
               OR article.summary CONTAINS markdown characters ('**', '*', '#', '`')

  oversized := LEN(rendered_html(input.articles)) > 102_000 bytes

  duplicate := ANY article IN input.articles WHERE
               article.url IN input.edition_history.sent_article_urls

  RETURN stale OR truncated OR oversized OR duplicate
END FUNCTION
```

### Examples

- **Stale article**: A December 2023 article about "GPT-4 launch" scores 0.72 relevance for GenAI topic but is 6 months old — it should be excluded entirely or penalized below threshold
- **Truncated summary**: LLM returns `"OpenAI announced a new reasoning model that can solve complex math problems. The model, called o3, achieves state-of-the-art results on benchm"` — cut off at 120 tokens mid-word
- **Markdown in summary**: LLM returns `"**Breaking:** Apple released iOS 18.2 with *major* AI features..."` — bold/italic markdown renders incorrectly in HTML email
- **Oversized email**: 10 articles × ~12 KB per article card = ~120 KB HTML, exceeding Gmail's 102 KB clip limit
- **Duplicate article**: "Bitcoin hits $100K" was sent on Monday, appears again in Wednesday's edition because the pipeline re-fetches and re-ranks without history awareness

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Articles less than 3 days old that are topically relevant continue to be included based on relevance scoring and balanced topic distribution
- Well-formed summaries (complete sentences, no markdown) are used as-is without modification
- Each article card continues to render with full title, metadata, summary, source link, and feedback buttons
- User topic preferences drive balanced distribution across selected articles
- Admin-approved articles are prioritized in the final newsletter (subject to freshness filtering)
- Feedback boost system continues to apply source-level adjustments during ranking
- Articles not previously sent remain candidates based on relevance, recency, and topic distribution

**Scope:**
All inputs that do NOT involve stale articles, summary formatting issues, email size overflow, or cross-edition duplicates should be completely unaffected by this fix. This includes:
- Mouse/click interactions with the newsletter
- Subscription management (subscribe/unsubscribe)
- Admin review queue workflow (stage → review → approve/reject → send)
- Feedback URL generation and logging

## Hypothesized Root Cause

Based on the bug description, the most likely issues are:

1. **Missing `from` parameter in NewsAPI call**: `fetch_from_newsapi()` does not pass a `from` date, so NewsAPI returns articles of any age. The `sortBy=publishedAt` only orders results; it doesn't filter.

2. **No date parsing or filtering in RSS fetch**: `fetch_from_rss()` stores `entry.get("published", "")` but never parses or filters it. Old RSS entries with high relevance pass through.

3. **No recency weighting in scoring**: `score_relevance()` uses only cosine similarity. A topically perfect but stale article scores identically to a fresh one.

4. **Insufficient token budget for summaries**: `max_tokens=120` in `summarize_article()` is too low for 2–3 complete sentences (which typically need 150–200 tokens). The LLM output gets hard-cut by the API.

5. **No post-processing of LLM output**: The summary is used verbatim after `.strip()`. No markdown stripping, no incomplete-sentence trimming.

6. **Fixed article count ignores email size**: `process_articles()` always targets `top_n=10` with `min_articles=8`. The template renders all articles with full styling, pushing total HTML well past 102 KB.

7. **No sent-article history**: The database has no table tracking which articles were sent to which users. The pipeline re-fetches and re-ranks from scratch each run.

## Correctness Properties

Property 1: Bug Condition — Freshness Filtering

_For any_ article where `published_at` is older than the freshness window (3 days default, 5 days fallback), the pipeline SHALL exclude it from the candidate pool before relevance scoring, ensuring no stale articles appear in the final newsletter.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Bug Condition — Summary Completeness and Formatting

_For any_ article summary produced by `summarize_article()`, the output SHALL end on a complete sentence (terminal punctuation: `.`, `!`, or `?`) and SHALL NOT contain markdown formatting characters (`**`, `*`, `#`, `` ` ``).

**Validates: Requirements 2.4, 2.5**

Property 3: Bug Condition — Email Size Compliance

_For any_ rendered newsletter HTML, the total size in bytes (UTF-8 encoded) SHALL NOT exceed 102,000 bytes. The system SHALL reduce article count (minimum 5) to stay within this limit.

**Validates: Requirements 2.6**

Property 4: Bug Condition — Cross-Edition Deduplication

_For any_ article that was included in a previous newsletter edition sent to the same user, the pipeline SHALL exclude it from candidate selection for subsequent editions.

**Validates: Requirements 2.7**

Property 5: Preservation — Relevance Scoring and Topic Distribution

_For any_ input where all articles are fresh (within 3 days), summaries are well-formed, email is under size limit, and no duplicates exist, the fixed pipeline SHALL produce the same article selection as the original pipeline, preserving relevance scoring, balanced topic distribution, and feedback boosts.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**

## Fix Implementation

### Changes Required

**File**: `tldr-newsletter/db.py`

**New Table**: `sent_articles` — tracks every article URL sent to each user for cross-edition deduplication.

```python
# New table creation in init_db()
conn.execute("""
    CREATE TABLE IF NOT EXISTS sent_articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        article_url TEXT NOT NULL,
        sent_at TEXT NOT NULL,
        run_id TEXT,
        UNIQUE(email, article_url)
    )
""")
CREATE INDEX IF NOT EXISTS idx_sent_articles_email ON sent_articles(email);
```

**New Functions**:
- `log_sent_articles(email: str, article_urls: list[str], run_id: str | None = None)` — bulk insert sent articles
- `get_sent_article_urls(email: str) -> set[str]` — return all previously sent article URLs for a user
- `clean_old_sent_articles(days: int = 90)` — prune entries older than 90 days to prevent unbounded growth

---

**File**: `tldr-newsletter/fetcher.py`

**Function**: `fetch_from_newsapi()`

**Specific Changes**:
1. **Add `from` parameter**: Pass `from` = ISO date string for 3 days ago to the NewsAPI params dict
2. **Add `freshness_days` parameter**: Accept an optional `freshness_days=3` parameter with a 5-day fallback option

```python
from datetime import datetime, timedelta, timezone

def fetch_from_newsapi(topic: str, page_size: int = 20, freshness_days: int = 3) -> list[dict]:
    # ... existing code ...
    from_date = (datetime.now(timezone.utc) - timedelta(days=freshness_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "q": query,
        "from": from_date,  # NEW: limits results to recent articles
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": page_size,
        "apiKey": NEWS_API_KEY,
    }
```

**Function**: `fetch_from_rss()`

**Specific Changes**:
1. **Parse `published_at` dates**: Use `dateutil.parser.parse()` to handle RSS date formats
2. **Filter by freshness window**: Skip entries older than `freshness_days`

```python
from dateutil import parser as dateutil_parser

def fetch_from_rss(topic: str, max_per_feed: int = 10, freshness_days: int = 3) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=freshness_days)
    # ... in the loop ...
    pub_date_str = entry.get("published", "")
    if pub_date_str:
        try:
            pub_date = dateutil_parser.parse(pub_date_str)
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)
            if pub_date < cutoff:
                continue  # Skip stale articles
        except (ValueError, TypeError):
            pass  # If unparseable, include it (benefit of the doubt)
```

**Function**: `fetch_articles_for_topics()`

**Specific Changes**:
1. Add `freshness_days` parameter, default 3
2. Pass through to both `fetch_from_newsapi()` and `fetch_from_rss()`

---

**File**: `tldr-newsletter/nlp_pipeline.py`

**Function**: `score_relevance()`

**Specific Changes**:
1. **Add recency decay factor**: Multiply cosine similarity by a decay multiplier based on article age

**Recency Decay Formula**:
```python
def _recency_decay(published_at: str, half_life_hours: float = 36.0) -> float:
    """
    Exponential decay: score_multiplier = 0.5 ^ (age_hours / half_life_hours)
    
    Examples:
      - 0 hours old  → multiplier = 1.0
      - 36 hours old → multiplier = 0.5
      - 72 hours old → multiplier = 0.25
      - 5 days old   → multiplier ≈ 0.1
    
    Articles at the edge of the 3-day window get ~0.25x their raw score.
    A stale article would need raw cosine > 0.3/0.25 = 1.2 (impossible) to pass threshold.
    """
    try:
        pub_dt = dateutil_parser.parse(published_at)
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
        age_hours = max(0, age_hours)
        return 0.5 ** (age_hours / half_life_hours)
    except (ValueError, TypeError):
        return 0.7  # Unknown date gets a moderate penalty
```

**Updated scoring**:
```python
score = float(util.cos_sim(topic_embedding, article_embedding))
decay = _recency_decay(article.get("published_at", ""))
final_score = round(score * decay, 4)
scored.append({**article, "relevance_score": final_score})
```

**Function**: `summarize_article()`

**Specific Changes**:
1. **Increase `max_tokens`** from 120 to 250
2. **Add post-processing function** `_clean_summary(text: str) -> str` that:
   - Strips markdown: removes `**`, `*`, `#`, `` ` ``, `---`, `> ` quote prefixes
   - Trims trailing incomplete sentence: if text doesn't end with `.`, `!`, or `?`, find the last sentence boundary and truncate there
   - Strips leading/trailing whitespace

**Summary Post-Processing Logic**:
```python
import re

def _clean_summary(text: str) -> str:
    """Strip markdown and ensure summary ends on a complete sentence."""
    # Remove markdown formatting
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
        # Find last sentence boundary
        last_period = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
        if last_period > 0:
            text = text[:last_period + 1]
    
    return text.strip()
```

**Function**: `process_articles()`

**Specific Changes**:
1. **Make `top_n` flexible**: Change default from 10 to a range (5–10) based on number of user topics
2. **Remove aggressive threshold lowering**: Instead of dropping to 0.05, accept fewer articles
3. **Add `max_email_bytes` parameter** (default 95000) to leave headroom below Gmail's 102 KB limit

```python
def process_articles(
    articles: list[dict],
    user_topics: list[str],
    top_n: int = 10,
    min_articles: int = 5,   # Changed from 8 to 5
    feedback_boost: dict[str, float] | None = None,
    sent_urls: set[str] | None = None,  # NEW: cross-edition dedup
) -> list[dict]:
```

4. **Filter out previously sent articles** early in the function:
```python
if sent_urls:
    articles = [a for a in articles if a.get("url") not in sent_urls]
```

---

**File**: `tldr-newsletter/newsletter_builder.py`

**Function**: `build_html()`

**Specific Changes**:
1. **Add size check**: After rendering, check byte length. If > 95,000 bytes, re-render with fewer articles (remove last article, re-render, repeat until under limit or at 5 articles minimum)
2. **Add `max_bytes` parameter** (default 95000)

```python
def build_html(user_name: str, user_email: str, topics: list[str], articles: list[dict], max_bytes: int = 95000) -> str:
    # ... render template ...
    html = template.render(...)
    
    # Size guard: reduce articles if HTML exceeds Gmail clip limit
    while len(html.encode('utf-8')) > max_bytes and len(articles) > 5:
        articles = articles[:-1]  # Drop lowest-ranked (last) article
        html = template.render(...)  # Re-render with fewer articles
    
    return html
```

---

**File**: `tldr-newsletter/pipeline.py`

**Specific Changes**:
1. **Pass `freshness_days` to fetch calls**: Use 3-day default, with fallback logic to retry at 5 days if insufficient articles
2. **Pass `sent_urls` to `process_articles()`**: Query `get_sent_article_urls(email)` before processing
3. **Log sent articles after send**: Call `log_sent_articles()` after successful email delivery
4. **Update `MIN_ARTICLES` constant** from 8 to 5
5. **Add freshness fallback logic**: If 3-day window yields fewer than `min_articles` quality candidates, retry with 5-day window

```python
# In send_pipeline(), before process_articles():
from db import get_sent_article_urls, log_sent_articles

sent_urls = get_sent_article_urls(user["email"])

# After successful send:
article_urls = [a["url"] for a in enriched]
log_sent_articles(user["email"], article_urls, run_id=run_id)
```

---

**File**: `tldr-newsletter/templates/newsletter.html`

**Specific Changes**:
1. **Inline only essential CSS**: Move non-critical decorative CSS to a minimal set to reduce per-article byte cost
2. **Remove redundant inline styles from footer**: The footer has duplicated style attributes that can be consolidated
3. **Estimated savings**: ~2–3 KB reduction in base template overhead (minor but helpful)

Note: The primary size control is the flexible article count in `newsletter_builder.py`, not template surgery.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bugs on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that exercise each bug condition against the current unfixed code to observe failures and confirm root causes.

**Test Cases**:
1. **Stale Article Inclusion Test**: Call `fetch_from_newsapi("GenAI")` and verify that articles older than 3 days are returned (will demonstrate bug on unfixed code)
2. **RSS No-Filter Test**: Call `fetch_from_rss("Tech")` and check for articles with `published_at` older than 3 days in results (will demonstrate bug on unfixed code)
3. **Summary Truncation Test**: Call `summarize_article()` with a complex article and check if output ends mid-sentence (will demonstrate bug on unfixed code)
4. **Markdown Leakage Test**: Call `summarize_article()` with articles that tend to produce markdown-heavy responses and check for `**`, `*`, `#` in output (will demonstrate bug on unfixed code)
5. **Email Size Test**: Build a newsletter with 10 articles using `build_html()` and measure byte size (will demonstrate > 102 KB on unfixed code)
6. **No Dedup Test**: Run pipeline twice with overlapping article pools and verify same URLs appear in both editions (will demonstrate bug on unfixed code)

**Expected Counterexamples**:
- NewsAPI returns articles from weeks/months ago that score high on relevance
- RSS feeds contain entries from 2023 that pass through unfiltered
- Summaries cut off at exactly 120 tokens regardless of sentence boundaries
- LLM occasionally wraps key terms in `**bold**` markdown
- 10-article newsletters consistently exceed 102 KB
- Same article URL appears in consecutive editions for the same user

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed functions produce the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := pipeline_fixed(input)
  ASSERT all articles in result.newsletter have published_at within freshness window
  ASSERT all summaries end on complete sentence AND contain no markdown
  ASSERT LEN(result.html.encode('utf-8')) <= 102000
  ASSERT no article URL in result.newsletter exists in user's sent_articles history
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed functions produce the same result as the original functions.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT pipeline_original(input).selected_articles == pipeline_fixed(input).selected_articles
  ASSERT pipeline_original(input).summaries == pipeline_fixed(input).summaries
  ASSERT pipeline_original(input).topic_distribution == pipeline_fixed(input).topic_distribution
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many random article configurations (varying ages, scores, topics) to verify scoring consistency
- It catches edge cases where the recency decay might inadvertently change selection for fresh articles
- It provides strong guarantees that feedback boosts, admin approvals, and topic balancing remain unchanged

**Test Plan**: Observe behavior on UNFIXED code first for fresh, well-formed articles, then write property-based tests capturing that behavior persists after the fix.

**Test Cases**:
1. **Fresh Article Scoring Preservation**: For articles < 24 hours old, verify relevance scores are nearly unchanged (decay ≈ 0.7–1.0 multiplier)
2. **Topic Distribution Preservation**: Verify `_balanced_select()` produces the same allocation with fresh articles
3. **Feedback Boost Preservation**: Verify source boosts continue to adjust rankings identically
4. **Admin Approval Preservation**: Verify approved articles still take priority in final selection
5. **Well-Formed Summary Preservation**: Verify `_clean_summary()` passes through text that already ends on a complete sentence with no markdown

### Unit Tests

- Test `_recency_decay()` with known ages: 0h → 1.0, 36h → 0.5, 72h → 0.25
- Test `_clean_summary()` strips `**bold**` → `bold`, `*italic*` → `italic`, `# Header` → `Header`
- Test `_clean_summary()` trims incomplete trailing sentence: `"First sentence. Second sent"` → `"First sentence."`
- Test `_clean_summary()` passes through already-clean text unchanged
- Test `fetch_from_newsapi()` includes `from` parameter in request
- Test `fetch_from_rss()` filters out articles older than `freshness_days`
- Test `build_html()` size guard reduces article count when HTML exceeds limit
- Test `get_sent_article_urls()` returns correct URL set from DB
- Test `log_sent_articles()` correctly inserts records with UNIQUE constraint

### Property-Based Tests

- Generate random article sets with varying `published_at` dates and verify no article older than `freshness_days` passes through `fetch_from_rss()` after filtering
- Generate random summary strings with various markdown patterns and verify `_clean_summary()` output never contains markdown characters and always ends on terminal punctuation
- Generate random article lists of varying lengths and verify `build_html()` output never exceeds `max_bytes` and always contains at least 5 articles (if 5+ provided)
- Generate random `sent_urls` sets and article pools, verify `process_articles()` never returns a URL in `sent_urls`
- Generate fresh articles (age < 12h) and verify `score_relevance()` with decay produces scores within 85–100% of raw cosine similarity

### Integration Tests

- Test full pipeline with a mix of fresh and stale articles, verify only fresh articles appear in final email
- Test pipeline run → log sent articles → second pipeline run, verify no duplicates in second edition
- Test newsletter rendering with 12 high-quality articles, verify output is under 102 KB and contains 5–10 articles
- Test freshness fallback: provide only 2 articles within 3 days, verify system retries with 5-day window and includes up to 5 articles
- Test admin-approved stale article: verify freshness filter still applies (admin approval does not override freshness)
