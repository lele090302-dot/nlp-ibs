# Implementation Plan: Spam Source Blocklist

## Tasks

**Quick Reference:**
- Task 1: Write bug condition exploration test (Property 1)
- Task 2: Write preservation property tests (Property 2)
- Task 3: Implement spam source blocklist fix
- Task 4: Verify bug condition exploration test now passes
- Task 5: Verify preservation tests still pass
- Task 6: Checkpoint - ensure all tests pass

---

## Overview

This task list implements the spam source blocklist fix following the exploratory bugfix workflow:

1. **Explore** - Write property tests BEFORE the fix to understand the bug (Property 1: Bug Condition)
2. **Preserve** - Write tests for legitimate behavior BEFORE the fix (Property 2: Preservation)
3. **Implement** - Apply the fix based on understanding from exploration
4. **Validate** - Verify the fix works and doesn't break anything

---

## Phase 1: Exploration

- [ ] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Spam Sources Currently Accepted
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **GOAL**: Surface counterexamples that demonstrate spam sources (Biztoc, Yahoo Finance) are currently accepted from NewsAPI
  - **Scoped PBT Approach**: For this deterministic bug, scope the property to concrete failing cases - articles with spam source names like "Biztoc" and "Yahoo Finance"
  - Test implementation details from Bug Condition in design.md:
    - Mock NewsAPI response with articles containing blocked sources (Biztoc, Yahoo Finance)
    - Call `fetch_from_newsapi()` with mocked API response
    - Assert that spam articles ARE included in the returned list (this is the current defective behavior)
    - For multiple articles: 50% legitimate sources (TechCrunch), 50% spam (Biztoc)
    - Verify all articles are returned, including spam ones
  - The test assertions should match the Expected Behavior from design (once fixed, spam should NOT be returned)
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found: "NewsAPI response with Biztoc articles returns them; response with Yahoo Finance articles returns them; no filtering occurs"
  - Mark task complete when test is written, run on unfixed code, and failure is documented
  - _Requirements: 1.1, 1.2_

---

## Phase 2: Preservation

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Legitimate Sources Pass Through Unchanged
  - **IMPORTANT**: Follow observation-first methodology:
    - Observe behavior on UNFIXED code for non-buggy inputs (legitimate sources)
    - Write property-based tests that assert observed behavior patterns
  - Test implementation details from Preservation Requirements in design.md:
    - Legitimate sources to test: TechCrunch, VentureBeat, Ars Technica, The Verge, Hacker News, etc.
    - For each legitimate source, call `fetch_from_newsapi()` and verify articles are returned
    - Property-based test: Generate random combinations of legitimate sources with various article metadata
    - For all non-blocked sources, assert returned article matches input article exactly:
      - title, url, source, description, content, published_at, topic all match
    - Verify RSS feeds continue to work (test `fetch_from_rss()` returns articles unchanged)
    - Verify deduplication logic works on non-blocked articles
  - Property-based testing generates many test cases automatically:
    - Random source names from legitimate set
    - Random article titles, descriptions, content (including special characters, unicode)
    - Random publication dates and metadata
    - Multiple topic combinations
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run on unfixed code, and passing
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

---

## Phase 3: Implementation

- [ ] 3. Implement spam source blocklist fix
  
  - [ ] 3.1 Create spam sources blocklist configuration file
    - Create new file: `config/spam_sources.yaml`
    - Add structure with `blocked_sources` list containing:
      - Biztoc (the primary spam source currently causing issues)
      - Yahoo Finance (redirects/low quality headlines)
      - Investor's Business Daily (frequent low-quality content)
    - Include comments explaining why each source is blocked
    - Make file human-readable and version-controllable
    - Verify YAML syntax is valid
    - _References: Design Section "File 2: config/spam_sources.yaml"_
    - _Bug_Condition: Articles from spam sources in blocklist_
    - _Expected_Behavior: Spam sources are filtered out, not returned from fetch_from_newsapi()_
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 3.2 Implement blocklist loading in fetcher.py
    - Add module-level variable: `_SPAM_BLOCKLIST = set()`
    - Add function: `load_spam_blocklist()`
      - Read `config/spam_sources.yaml` (or path from `SPAM_BLOCKLIST_PATH` env var)
      - Parse YAML and extract `blocked_sources` list
      - Convert to lowercase set for case-insensitive O(1) lookup
      - Log successful load: "Loaded spam blocklist with X sources"
      - Handle FileNotFoundError: log warning and return empty set (fail-open)
      - Handle YAML parse errors: log warning and return empty set
    - Call `load_spam_blocklist()` at module import time
    - Add function: `reload_blocklist()`
      - Allow runtime reload of blocklist without restarting service
      - Update module-level `_SPAM_BLOCKLIST` cache
    - _References: Design Section "Fix Implementation - File 1 (1), (2), (4), (5)"_
    - _Bug_Condition: Spam sources not currently validated against blocklist_
    - _Expected_Behavior: Blocklist loaded on startup and available for filtering_
    - _Requirements: 2.1, 2.4_

  - [ ] 3.3 Implement source filtering in fetch_from_newsapi()
    - Add import: `import yaml` (if not already present)
    - Locate the article processing loop in `fetch_from_newsapi()` (currently returns all articles)
    - Add source validation logic AFTER parsing the NewsAPI JSON response:
      - For each article in `resp.json()["articles"]`
      - Extract source name: `source_name = a.get("source", {}).get("name", "Unknown")`
      - Check: `if source_name.lower() in _SPAM_BLOCKLIST` (case-insensitive)
      - If matched: skip this article (continue to next), do not add to results list
      - If not matched: process article normally (convert to internal format and append)
    - Add debug logging: `logger.debug(f"[NewsAPI] Filtered spam source: {source_name}")` when article is skipped
    - Ensure the check happens BEFORE the internal article dict is created
    - Verify behavior:
      - Spam articles are completely excluded from returned list
      - Legitimate articles continue through unchanged
      - Metadata is preserved for non-blocked sources
    - _References: Design Section "Fix Implementation - File 1 (3)"_
    - _Bug_Condition: Articles from spam sources are currently not filtered_
    - _Expected_Behavior: isBugCondition from design - if source in blocklist, article not returned_
    - _Preservation: For non-blocked sources, articles returned identically as before_
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 3.4 Add environment variable configuration
    - Add to `tldr-newsletter/.env.example`:
      - `SPAM_BLOCKLIST_PATH=config/spam_sources.yaml`
    - Verify that `load_spam_blocklist()` uses `os.getenv("SPAM_BLOCKLIST_PATH", "config/spam_sources.yaml")`
    - Test that the function respects the environment variable when set
    - _References: Design Section "Fix Implementation - File 3"_
    - _Requirements: 2.4_

  - [ ] 3.5 Add error handling and logging
    - Ensure blocklist loading includes try/catch for I/O and parsing errors
    - Log all filtered articles at DEBUG level for audit trail
    - Log blocklist load status (success/failure) at INFO level
    - Verify function doesn't crash if blocklist file is missing (fail-open, use empty blocklist)
    - Verify function doesn't crash if blocklist file is malformed YAML
    - Test that appropriate warnings are logged when config is unavailable
    - _References: Design Section "Fix Implementation - File 1 (5)"_
    - _Requirements: 2.1, 2.4_

---

## Phase 4: Validation

- [ ] 4. Verify bug condition exploration test now passes
  - **Property 1: Expected Behavior** - Spam Sources Now Filtered
  - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
  - The test from task 1 encodes the expected behavior (spam should NOT be returned)
  - When this test passes, it confirms the expected behavior is satisfied
  - Steps:
    - Run the bug condition exploration test from task 1 again
    - Test should now assert that spam articles ARE filtered out
    - Mock NewsAPI response with Biztoc articles
    - Call fixed `fetch_from_newsapi()`
    - Assert that Biztoc articles are NOT in results
    - Assert that debug logs contain "Filtered spam source: Biztoc"
  - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
  - Verify with multiple spam sources: Biztoc, Yahoo Finance, Investor's Business Daily
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 5. Verify preservation tests still pass
  - **Property 2: Preservation** - Legitimate Sources Still Pass Through
  - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
  - Run preservation property tests from task 2
  - Verify:
    - TechCrunch articles returned unchanged
    - VentureBeat articles returned with correct metadata
    - Multiple legitimate sources all returned with identical metadata
    - Metadata integrity: special characters, unicode, long fields preserved
    - RSS feeds still work via `fetch_from_rss()`
    - Deduplication logic still works on non-blocked articles
  - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
  - Confirm all tests still pass after fix (no regressions)
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

---

## Phase 5: Checkpoint

- [ ] 6. Checkpoint - Ensure all tests pass and implementation is complete
  - [ ] 6.1 Run full test suite
    - Run all unit tests for blocklist loading
    - Run all property-based tests (Bug Condition and Preservation)
    - Run integration tests: full pipeline with spam sources present
    - Verify no tests are skipped or broken
    - Verify test coverage includes:
      - Spam source filtering (Biztoc, Yahoo Finance, etc.)
      - Legitimate source preservation (TechCrunch, VentureBeat, etc.)
      - Blocklist loading and parsing
      - Case-insensitive source matching
      - Missing/malformed blocklist handling
      - Audit logging of filtered articles

  - [ ] 6.2 Verify implementation against design requirements
    - Configuration file created at `config/spam_sources.yaml`
    - `load_spam_blocklist()` function implemented and working
    - `reload_blocklist()` function implemented and callable
    - Source filtering in `fetch_from_newsapi()` implemented
    - Environment variable `SPAM_BLOCKLIST_PATH` configurable
    - Error handling for missing/malformed files in place
    - Logging at appropriate levels (DEBUG for filtered articles, INFO for load status)
    - Case-insensitive source matching working

  - [ ] 6.3 Verify preservation of non-blocked behavior
    - RSS feeds continue to work (no filtering in `fetch_from_rss()`)
    - Deduplication logic unchanged
    - Article metadata passed through unchanged for legitimate sources
    - No performance degradation for non-blocked sources
    - All legitimate sources in TOPIC_KEYWORDS continue to work

  - [ ] 6.4 Manual verification checklist
    - [ ] Start fetcher service with blocklist config file present
    - [ ] Fetch articles for a topic and verify Biztoc articles do NOT appear
    - [ ] Verify legitimate sources (TechCrunch, VentureBeat) DO appear
    - [ ] Check logs for "Filtered spam source" debug messages
    - [ ] Remove blocklist file and verify fetcher logs warning but doesn't crash
    - [ ] Add a new spam source to blocklist and restart; verify it's filtered
    - [ ] Update .env with `SPAM_BLOCKLIST_PATH=custom/path.yaml` and verify it loads from custom path

  - [ ] 6.5 Confirm blocklist is maintainable
    - [ ] Blocklist is in human-readable YAML format
    - [ ] Adding new spam sources requires only editing the YAML, no code changes
    - [ ] Comments in YAML explain why each source is blocked
    - [ ] File is version-controllable (in git)
    - [ ] Deployment process documented for updating blocklist

  - Mark task complete when:
    - All tests pass (unit, property-based, integration)
    - All implementation requirements met
    - No regressions detected
    - Preservation tests confirm legitimate behavior unchanged
    - All manual verification steps pass

---

## Testing Summary

### Property-Based Tests Required

**Property 1: Bug Condition - Spam Source Filtering**
- Framework: Hypothesis (Python property-based testing)
- Input: Mocked NewsAPI responses with spam source articles
- Assertion: On UNFIXED code: articles are returned (FAIL expected); On FIXED code: articles are filtered out (PASS)
- Coverage: Biztoc, Yahoo Finance, Investor's Business Daily, case variations
- Documentation: Document counterexamples that demonstrate the bug

**Property 2: Preservation - Legitimate Source Pass-Through**
- Framework: Hypothesis
- Input: Generated random legitimate sources and article metadata
- Assertion: Fixed function returns identical results to original function for non-blocked sources
- Coverage: TechCrunch, VentureBeat, Ars Technica, The Verge, Hacker News, other legitimate sources
- Verification: Metadata fields match exactly (title, url, source, description, content, topic, published_at)

### Unit Tests Required

- `test_load_spam_blocklist_valid()` - Blocklist loads correctly from YAML
- `test_load_spam_blocklist_missing_file()` - Missing file doesn't crash (fail-open)
- `test_load_spam_blocklist_malformed_yaml()` - Malformed YAML doesn't crash
- `test_reload_blocklist()` - Runtime reload updates cached blocklist
- `test_source_matching_case_insensitive()` - "BIZTOC" matches "biztoc"
- `test_spam_article_filtered()` - Article with spam source is excluded
- `test_legitimate_article_included()` - Article with non-blocked source is included
- `test_filtered_article_logged()` - Debug log written when article filtered
- `test_environment_variable_override()` - Custom `SPAM_BLOCKLIST_PATH` is used

### Integration Tests Required

- Full pipeline with spam sources: fetch → deduplicate → review queue; verify spam never appears
- Multiple topics simultaneously; verify spam filtering applied per topic
- Realistic NewsAPI responses with mixed legitimate/spam sources
- Blocklist update takes effect across multiple sequential fetches

---

## Task Dependency Graph

```json
{
  "waves": [
    {
      "name": "Phase 1: Exploration (Parallel)",
      "tasks": ["1. Write bug condition exploration test", "2. Write preservation property tests"],
      "reason": "These run on unfixed code to establish baseline defective behavior and preservation requirements"
    },
    {
      "name": "Phase 2: Implementation",
      "tasks": ["3. Implement spam source blocklist fix"],
      "dependsOn": ["Phase 1: Exploration (Parallel)"],
      "reason": "Requires understanding from exploration phase before implementing fix"
    },
    {
      "name": "Phase 3: Validation",
      "tasks": ["4. Verify bug condition exploration test now passes", "5. Verify preservation tests still pass"],
      "dependsOn": ["Phase 2: Implementation"],
      "reason": "Verifies the fix works and doesn't cause regressions"
    },
    {
      "name": "Phase 4: Checkpoint",
      "tasks": ["6. Checkpoint - Ensure all tests pass and implementation is complete"],
      "dependsOn": ["Phase 3: Validation"],
      "reason": "Final gate: all tests passing and no regressions detected"
    }
  ]
}
```

**Task Execution Order:**

1. **Wave 1 (Parallel)**: Tasks 1 and 2 can run in parallel on unfixed code
2. **Wave 2 (Sequential)**: Task 3 applies the fix (depends on completing Wave 1)
3. **Wave 3 (Parallel)**: Tasks 4 and 5 can run in parallel to verify the fix
4. **Wave 4 (Final)**: Task 6 ensures all tests pass before declaring completion

---

## Notes

### Key Points

- **Bugfix Methodology**: This follows the exploratory bugfix workflow - test FIRST, then fix, then verify
- **Property-Based Testing**: Hypothesis is used for both bug condition (showing the bug exists) and preservation (showing legitimate behavior unchanged)
- **Fail-Open Strategy**: If blocklist config is missing/broken, the system logs a warning and proceeds with an empty blocklist rather than crashing
- **Audit Trail**: All filtered articles are logged at DEBUG level for troubleshooting
- **Case Insensitivity**: Source names are compared case-insensitively to catch variations like "BIZTOC" vs "Biztoc"

### Files Modified

1. **tldr-newsletter/fetcher.py** - Add blocklist loading, filtering logic, error handling
2. **config/spam_sources.yaml** - New YAML configuration file (must be created)
3. **tldr-newsletter/.env.example** - Add `SPAM_BLOCKLIST_PATH` environment variable

### Environment

- Language: Python 3.x
- Key Dependency: PyYAML (for parsing blocklist config)
- Testing Framework: pytest + Hypothesis
- Mock Framework: unittest.mock or pytest-mock

### Context from Design Document

- **Root Cause**: Missing validation layer; no blocklist configuration; manual admin burden; no extensibility mechanism
- **Fix Strategy**: YAML-based blocklist + loading on module init + filtering in fetch_from_newsapi()
- **Preservation Strategy**: RSS feeds unaffected; deduplication logic unaffected; legitimate sources pass through unchanged
- **Correctness Properties**: Property 1 ensures spam filtered; Property 2 ensures legitimate sources unaffected

