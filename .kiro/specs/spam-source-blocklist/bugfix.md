# Bugfix Requirements Document

## Introduction

The TL;DR Newsletter pipeline accepts articles from all sources returned by NewsAPI without validation, allowing spam sources like Biztoc.com to enter the fetching pipeline. Biztoc.com articles are known to redirect to non-official websites and provide no reader value. These spam articles pass through the review queue and eventually appear in newsletters, degrading subscriber experience and damaging newsletter credibility. The fetcher must implement source validation to block known spam sources before articles are processed further.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN articles are fetched via `fetch_from_newsapi()` THEN the system accepts articles from any source returned by the API without checking against a blocklist, including spam sources like Biztoc.com

1.2 WHEN Biztoc.com articles are accepted THEN the system treats them identically to legitimate sources, allowing them to pass through to the review queue with full title, URL, and metadata

1.3 WHEN articles from spam sources reach the admin review queue THEN the admin must manually identify and reject them, consuming editorial time that should focus on legitimate content curation

1.4 WHEN spam articles are reviewed and approved (or accidentally approved) THEN the system includes them in the newsletter sent to subscribers, exposing readers to unreliable redirect links

### Expected Behavior (Correct)

2.1 WHEN articles are fetched via `fetch_from_newsapi()` THEN the system SHALL check the article source against a maintained blocklist and discard any articles from blocked sources before returning results

2.2 WHEN an article source is on the blocklist (e.g., "Biztoc") THEN the system SHALL filter it out during the fetch phase, preventing it from reaching the review queue or pipeline

2.3 WHEN articles are returned from `fetch_from_newsapi()` THEN the system SHALL only include articles from sources that are not in the blocklist, ensuring zero spam articles reach downstream processing

2.4 WHEN the blocklist is updated or extended with new spam sources THEN the system SHALL apply the updated blocklist to all subsequent fetches without requiring code changes or redeployment of the fetcher module

### Unchanged Behavior (Regression Prevention)

3.1 WHEN articles are from legitimate sources (e.g., TechCrunch, VentureBeat, The Verge) THEN the system SHALL CONTINUE TO accept and process them without any filtering or rejection

3.2 WHEN articles are fetched from RSS feeds via `fetch_from_rss()` THEN the system SHALL CONTINUE TO process them without source-based filtering (assuming RSS feeds are curated and trustworthy)

3.3 WHEN the `deduplicate()` function processes articles THEN the system SHALL CONTINUE TO remove duplicates by URL and near-duplicate titles as before, independent of source blocking

3.4 WHEN the review queue is populated with articles THEN the system SHALL CONTINUE TO rank approved articles by relevance score and display them for admin review, with the difference that spam sources will never appear in the queue

3.5 WHEN users receive newsletters THEN the system SHALL CONTINUE TO send high-quality articles from legitimate sources with full summaries, metadata, and feedback controls, with spam articles permanently excluded
