# Bugfix Requirements Document

## Introduction

Subscribers are receiving far fewer articles than the guaranteed minimum. The system defines MIN_ARTICLES=5 and promises 5-10 articles per newsletter, but most users with niche topics receive only 2-4 articles. This is caused by two compounding issues: (1) several RSS feed URLs in `fetcher.py` are broken HTML pages rather than valid RSS feeds, reducing the source pool, and (2) the relevance threshold filter in `nlp_pipeline.py` drops articles below the score cutoff with no enforcement mechanism to guarantee the minimum — the existing "warning" is just a print statement that takes no corrective action. The user wants the guaranteed minimum raised to 8 articles.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a subscriber has niche topics (e.g., Fintech, Startups) AND the RSS feeds for those topics include broken URLs that return HTML instead of valid RSS XML THEN the system silently returns zero articles from those feeds, drastically reducing the available article pool

1.2 WHEN the relevance threshold filter (RELEVANCE_THRESHOLD=0.2) removes articles AND the remaining count falls below MIN_ARTICLES THEN the system only prints a warning message and continues to deliver the insufficient number of articles

1.3 WHEN the fallback logic widens freshness from 5 to 7 days THEN the system checks raw article count before scoring/filtering, so the widening does not address the post-scoring deficit where most articles are actually lost

1.4 WHEN the semantic relevance scoring evaluates articles against user topics THEN the system uses short, narrow TOPIC_DESCRIPTIONS in nlp_pipeline.py (e.g., "generative artificial intelligence, large language models, GPT, AI tools, machine learning breakthroughs") which produces tight embeddings that fail to match many legitimately relevant articles using different terminology, inflating false negatives at the threshold filter

1.5 WHEN cross-edition deduplication removes previously sent articles from an already small source pool for niche topics THEN the system delivers as few as 2 articles with no corrective action to meet the minimum guarantee

1.6 WHEN feedparser.parse() encounters a broken or malformed feed (feed.bozo = 1) AND returns zero usable entries THEN the system never checks the bozo flag and silently proceeds as if the feed simply had no new articles, making it impossible to distinguish broken feeds from empty feeds

1.7 WHEN an RSS/Atom feed uses the "updated" field instead of "published" for entry dates THEN the system only checks entry.get("published", "") and stores an empty published_at string, causing _recency_decay to apply a 0.7 penalty multiplier to fresh articles as if their date were unparseable

1.8 WHEN feedparser.parse(feed_url) makes its internal HTTP request to fetch a feed THEN no timeout is configured, so a single slow or hanging RSS server can stall the entire fetch pipeline indefinitely (unlike NewsAPI calls which have timeout=10)

1.9 WHEN fetch_from_rss appends articles from RSS entries THEN it does not validate that title and link are non-empty (unlike fetch_from_newsapi which filters on a.get("title") and a.get("url")), allowing entries with blank titles or missing URLs to enter the pipeline, producing useless embeddings and broken newsletter links

### Expected Behavior (Correct)

2.1 WHEN RSS feeds are configured in the system THEN the system SHALL only contain valid RSS/Atom feed URLs that return parseable XML, removing or replacing broken HTML page URLs

2.2 WHEN the relevance threshold filter reduces the article count below the minimum (8 articles) THEN the system SHALL progressively lower the threshold or include lower-scored articles until the minimum is met or all available articles are exhausted

2.3 WHEN the fallback freshness widening is triggered THEN the system SHALL re-evaluate article count after scoring and filtering (not just after fetching), and continue widening or lowering thresholds until the minimum is met

2.4 WHEN cross-edition deduplication and all filtering combined result in fewer articles than the minimum (8) THEN the system SHALL relax constraints (threshold, freshness window, deduplication scope) in a defined priority order to reach the minimum before delivering the newsletter

2.5 WHEN the semantic relevance scoring evaluates articles against user topics THEN the system SHALL use expanded, richer keyword descriptions per topic (beyond current single-phrase mappings) to improve scoring accuracy and increase the number of articles that pass the relevance threshold

2.6 WHEN the system cannot meet the minimum of 8 articles after exhausting all fallback strategies THEN the system SHALL deliver all available articles (even if below the minimum) and log an explicit alert indicating the shortfall and which strategies were attempted

2.7 WHEN feedparser.parse() returns a result with feed.bozo = 1 AND zero usable entries THEN the system SHALL log a warning identifying the broken feed URL and the bozo_exception, skip that feed, and continue processing remaining feeds

2.8 WHEN an RSS/Atom feed entry does not have a "published" field THEN the system SHALL fall back to the "updated" field for the publication date before defaulting to an empty string, ensuring fresh Atom-feed articles receive accurate recency scoring

2.9 WHEN the system fetches an RSS feed via feedparser THEN the system SHALL enforce a timeout (matching the 10-second timeout used for NewsAPI calls) so that a single slow or unresponsive feed server cannot block the entire pipeline

2.10 WHEN fetch_from_rss processes RSS entries THEN the system SHALL validate that each entry has a non-empty title and a non-empty URL before appending it to the article list, consistent with the validation applied in fetch_from_newsapi

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a subscriber has broad topic subscriptions that produce abundant relevant articles THEN the system SHALL CONTINUE TO deliver no more than MAX_ARTICLES (10) articles, selected by highest relevance score

3.2 WHEN articles score above the relevance threshold AND the pool is sufficient THEN the system SHALL CONTINUE TO filter out low-relevance articles to maintain newsletter quality

3.3 WHEN an article has already been sent to a subscriber in a previous edition THEN the system SHALL CONTINUE TO exclude that article via cross-edition deduplication (dedup is only relaxed as a last resort when minimum cannot be met otherwise)

3.4 WHEN admin-approved articles exist AND meet the minimum count THEN the system SHALL CONTINUE TO prioritize admin-curated content over AI-selected articles

3.5 WHEN the balanced topic distribution selects articles THEN the system SHALL CONTINUE TO distribute slots fairly across the subscriber's topics
