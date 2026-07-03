# Bug Condition Analysis: Spam Source Blocklist

## Bug Condition Identification

This document applies the bug condition methodology to the spam source blocklist bugfix.

### Bug Condition Function: C(X)

Identifies inputs (articles) that trigger the bug:

```pascal
FUNCTION isBugCondition(article)
  INPUT: article of type Dict with keys {source, title, url, ...}
  OUTPUT: boolean
  
  // Bug is triggered when article source is a known spam source
  RETURN article.source IN BLOCKED_SOURCES
END FUNCTION
```

**Example:**
```pascal
isBugCondition({
  "source": "Biztoc",
  "title": "Breaking News...",
  "url": "https://biztoc.com/x/...",
  ...
}) = TRUE
```

### Property Specification: Fix Checking

Defines correct behavior for articles that trigger the bug:

```pascal
// Property: Spam Source Filtering
FOR ALL article WHERE isBugCondition(article) DO
  result ← fetch_from_newsapi'(...)  // F'(X) - fixed version
  ASSERT article NOT IN result
END FOR
```

**Interpretation:** After the fix is applied, when `fetch_from_newsapi()` is called and returns articles, no article with a source in the blocklist shall appear in the results.

### Property Specification: Preservation Checking

Ensures non-buggy inputs are unaffected:

```pascal
// Property: Legitimate Source Preservation
FOR ALL article WHERE NOT isBugCondition(article) DO
  result_original ← fetch_from_newsapi(...)      // F(X) - original
  result_fixed ← fetch_from_newsapi'(...)        // F'(X) - fixed
  ASSERT article IN result_original IMPLIES article IN result_fixed
END FOR
```

**Interpretation:** Articles from legitimate sources (those not in the blocklist) shall continue to be returned and processed exactly as before. The fix must not change behavior for non-spam sources.

## Bug Condition Taxonomy

| Category | Condition | Example |
|----------|-----------|---------|
| **Buggy Input (C(X))** | Source is spam | `article.source == "Biztoc"` |
| **Non-Buggy Input (¬C(X))** | Source is legitimate | `article.source == "TechCrunch"` |
| **Current Behavior (F)** | Accept all sources | Accepts Biztoc articles |
| **Expected Behavior (F')** | Filter spam sources | Rejects Biztoc articles |
| **Counterexample** | Concrete buggy input | Biztoc article reaching review queue |

## Correctness Properties

### Property 1: Zero Spam Articles in Results
```
∀ article ∈ fetch_from_newsapi'(topic)
  → article.source ∉ BLOCKED_SOURCES
```
**Meaning:** Every article returned by the fixed fetcher must have a source not in the blocklist.

### Property 2: All Legitimate Articles Included
```
∀ article_original ∈ fetch_from_newsapi(topic)
  ∧ article_original.source ∉ BLOCKED_SOURCES
  → article_original ∈ fetch_from_newsapi'(topic)
```
**Meaning:** Any legitimate article from the original implementation must still be present after the fix.

### Property 3: Blocklist Configurability
```
BLOCKLIST ⊆ Configuration
```
**Meaning:** The blocklist must be externally configurable (loaded from file or config, not hardcoded in fetcher.py) so new spam sources can be added without code changes.

## Implementation Approach

The fix should:

1. **Define a blocklist** - A list of known spam sources (initially containing "Biztoc")
2. **Load the blocklist** - From a configuration file or environment variable for easy updates
3. **Filter articles** - In `fetch_from_newsapi()`, check `article.source` against the blocklist before returning
4. **Maintain backward compatibility** - No changes to the function signature or return format for legitimate articles

## Test Strategy (Informative)

**Fix Checking Tests:**
- Assert that calling `fetch_from_newsapi()` with Biztoc in API results returns zero Biztoc articles
- Assert that spam articles are filtered before the list is returned to the caller

**Preservation Checking Tests:**
- Assert that legitimate sources (TechCrunch, VentureBeat, etc.) continue to be returned
- Assert that the number and content of non-spam articles remains unchanged
- Assert that deduplication and other processing steps still work for legitimate articles

## Related Acceptance Criteria

From the bugfix.md file, this analysis maps to:

| Acceptance Criterion | Bug Condition Relevance |
|---------------------|----------------------|
| 2.1 Check against blocklist | F'(X) - Core fix |
| 2.2 Filter blocked sources | C(X) identification |
| 2.3 Only unblocked articles returned | ∀article: ¬C(X) |
| 2.4 Blocklist configurability | Configuration requirement |
| 3.1 Legitimate sources accepted | ¬C(X) preservation |
| 3.2 RSS feeds unaffected | ¬C(X) in different context |
