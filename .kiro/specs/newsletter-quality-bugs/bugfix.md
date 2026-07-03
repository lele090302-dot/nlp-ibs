# Bugfix Requirements Document

## Introduction

The TL;DR Newsletter pipeline has three quality bugs that collectively degrade the reader experience. A stale article from December 2023 was included in today's edition due to missing date/freshness filtering. One article's summary was truncated mid-sentence and rendered in a different font due to an insufficient token limit and unstripped markdown formatting. The email was clipped by Gmail (the "..." / "View entire message" prompt) because the HTML exceeded Gmail's ~102 KB limit with 10 fully-styled articles. The user's stated priority is "quality over quantity" — fewer high-quality, recent articles with complete summaries is preferable to filling all 10 slots.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN articles are fetched via `fetch_from_newsapi()` THEN the system does not pass a `from` date parameter, allowing articles of any age to be returned

1.2 WHEN articles are fetched via `fetch_from_rss()` THEN the system does not filter by publication date, allowing arbitrarily old articles to enter the pipeline

1.3 WHEN `score_relevance()` evaluates articles THEN the system only checks cosine similarity to user topics without considering article recency, so a stale article that is topically relevant passes the threshold

1.4 WHEN `summarize_article()` generates a summary using `max_tokens=120` THEN the system may produce a summary that is truncated mid-sentence because 120 tokens is insufficient to guarantee complete sentences

1.5 WHEN the LLM returns summary text containing markdown formatting or special characters THEN the system does not strip this formatting before injecting into the HTML template, causing the summary to render in a different font or style than other articles

1.6 WHEN the newsletter is built THEN the system always targets exactly 8-10 articles regardless of available quality content, lowering relevance thresholds aggressively (to 0.05) to fill slots rather than sending fewer high-quality articles

1.7 WHEN an article was already featured in a previous newsletter edition THEN the system does not exclude it, allowing the same article to appear in consecutive editions

### Expected Behavior (Correct)

2.1 WHEN articles are fetched via `fetch_from_newsapi()` THEN the system SHALL pass a `from` date parameter limiting results to the past 3 days

2.2 WHEN articles are fetched via `fetch_from_rss()` THEN the system SHALL filter out any articles with a publication date older than 3 days

2.3 WHEN `score_relevance()` evaluates articles THEN the system SHALL incorporate a recency decay factor that penalizes older articles, so stale articles require a substantially higher topical match to pass the threshold

2.4 WHEN `summarize_article()` generates a summary THEN the system SHALL produce a self-contained 2-4 sentence summary that conveys the key news (who, what, why it matters) so a reader understands the story without clicking through, and SHALL ensure the summary ends on a complete sentence by using a sufficient token budget and post-processing to trim any trailing incomplete sentence

2.5 WHEN the LLM returns summary text THEN the system SHALL strip markdown formatting and special characters (e.g., `**`, `*`, `#`, backticks) before inserting the summary into the HTML template

2.6 WHEN building the newsletter THEN the system SHALL target 5-10 articles depending on the number of chosen topics and available quality content. If the 3-day freshness window does not yield enough quality articles for a topic, the system SHALL fall back to a 5-day window before accepting fewer articles. A single-topic subscriber may receive as few as 5 articles if that is all the quality content available within the freshness window.

2.7 WHEN an article was already featured in a previous newsletter edition THEN the system SHALL exclude it from candidate selection so that subscribers never receive the same article twice across editions

### Unchanged Behavior (Regression Prevention)

3.1 WHEN articles are less than 3 days old and topically relevant THEN the system SHALL CONTINUE TO include them based on relevance scoring and balanced topic distribution

3.2 WHEN `summarize_article()` produces a well-formed summary that ends on a complete sentence within the token budget THEN the system SHALL CONTINUE TO use that summary as-is without modification

3.3 WHEN the newsletter has articles within the freshness window THEN the system SHALL CONTINUE TO render each article with its full title, metadata, summary, source link, and feedback buttons

3.4 WHEN users have configured topic preferences THEN the system SHALL CONTINUE TO use balanced topic distribution when selecting articles

3.5 WHEN the admin has approved specific articles THEN the system SHALL CONTINUE TO prioritize admin-approved articles in the final newsletter (subject to freshness filtering)

3.6 WHEN the feedback boost system has source-level adjustments for a user THEN the system SHALL CONTINUE TO apply those boosts during article ranking

3.7 WHEN an article has not been featured in any previous edition THEN the system SHALL CONTINUE TO consider it as a candidate based on relevance, recency, and topic distribution
