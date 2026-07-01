# Requirements Document

## Introduction

The TL;DR newsletter pipeline currently copies article titles verbatim from their original publishers (NewsAPI, RSS feeds, and manually curated sources) and renders them unmodified in the newsletter HTML. Only the article body summary is rewritten by an LLM. This feature adds a title-rephrasing step to the pipeline so that every article displayed in the newsletter shows a rewritten headline instead of the original publisher's exact wording. The rephrased title must be crisp, catchy, and engaging while remaining serious enough for an academically-minded readership, free of jargon and abbreviations, and must not read as clickbait or tabloid-style. The rephrasing step runs after deduplication (which continues to rely on original titles) and after summarization has been introduced into the per-article enrichment loop, so that deduplication behavior is unaffected. The original publisher title is retained on the article record for debugging and administrative purposes, even though the newsletter only displays the rephrased title.

## Glossary

- **Title_Rephraser**: The pipeline component responsible for generating a rewritten version of an article's title using the Groq LLM client.
- **Article_Record**: The dictionary representing a single article as it flows through `fetcher.py` and `nlp_pipeline.py`, containing fields such as `title`, `url`, `source`, `description`, `content`, `topic`, and enrichment fields added during processing (e.g., `summary`, `reading_time`).
- **Original_Title**: The unmodified title text as retrieved from the source (NewsAPI, RSS, or manual JSON), stored on the Article_Record under the `original_title` field after rephrasing occurs.
- **Rephrased_Title**: The LLM-generated replacement headline text, stored on the Article_Record under the `title` field after rephrasing occurs.
- **NLP_Pipeline**: The module (`nlp_pipeline.py`) that orchestrates relevance scoring, threshold filtering, balanced topic selection, summarization, title rephrasing, and reading time estimation via `process_articles()`.
- **Fetcher**: The module (`fetcher.py`) responsible for retrieving articles from NewsAPI, RSS feeds, and the manual articles file, and for deduplicating them by URL and normalized title.
- **Groq_Client**: The Groq API client used by the NLP_Pipeline to make LLM completion requests.
- **Newsletter_Template**: The Jinja2 HTML template (`templates/newsletter.html`) that renders each Article_Record's title into the `.article-title` element.

## Requirements

### Requirement 1: Rephrase Article Titles

**User Story:** As a newsletter subscriber, I want article headlines to be rewritten rather than copied verbatim from the publisher, so that the newsletter content is original and avoids reproducing publisher headlines exactly.

#### Acceptance Criteria

1. WHEN the NLP_Pipeline enriches a selected article (an article chosen for inclusion in the newsletter after relevance filtering and balanced topic selection), THE Title_Rephraser SHALL generate a Rephrased_Title for that article using the Groq_Client.
2. WHEN the Title_Rephraser generates a Rephrased_Title, THE NLP_Pipeline SHALL store the Rephrased_Title in the Article_Record's `title` field.
3. WHEN the Title_Rephraser generates a Rephrased_Title, THE NLP_Pipeline SHALL store the Original_Title in the Article_Record's `original_title` field.
4. THE NLP_Pipeline SHALL invoke the Title_Rephraser for each selected article only after the Fetcher's deduplication step has completed and after that article's summary has been generated within the per-article enrichment loop.
5. IF the Groq_Client returns a Rephrased_Title that is empty or contains only whitespace, THEN THE Title_Rephraser SHALL discard that response and use a minimally cleaned version of the Original_Title as the Rephrased_Title, consistent with the fallback behavior defined in Requirement 3.
6. IF the Groq_Client returns a Rephrased_Title that is identical to the Original_Title after case-insensitive, whitespace-normalized comparison, THEN THE Title_Rephraser SHALL treat that response as a failure and use a minimally cleaned version of the Original_Title as the Rephrased_Title, consistent with the fallback behavior defined in Requirement 3.

### Requirement 2: Title Style Constraints

**User Story:** As a newsletter subscriber with an academic background, I want rephrased titles to be concise and engaging without being sensational, so that the newsletter maintains a credible, professional tone.

#### Acceptance Criteria

1. WHEN the Title_Rephraser generates a Rephrased_Title, THE Title_Rephraser SHALL instruct the Groq_Client to produce a title that is concise (no more than 100 characters) and engaging.
2. WHEN the Title_Rephraser generates a Rephrased_Title, THE Title_Rephraser SHALL instruct the Groq_Client to avoid clickbait or tabloid-style phrasing, including sensationalized language, multiple exclamation marks, ALL CAPS words, and hook-style unanswered questions.
3. WHEN the Title_Rephraser generates a Rephrased_Title, THE Title_Rephraser SHALL instruct the Groq_Client to avoid jargon and abbreviations, expanding any acronym that is not widely recognized by a general audience.
4. WHEN the Title_Rephraser generates a Rephrased_Title, THE Title_Rephraser SHALL instruct the Groq_Client to preserve the factual meaning of the Original_Title, including its named entities, numerical values, and core claim.
5. IF the Groq_Client returns a Rephrased_Title longer than 100 characters, THEN THE Title_Rephraser SHALL truncate the Rephrased_Title to 100 characters at the nearest preceding word boundary before storing it in the Article_Record's `title` field.

### Requirement 3: Fallback on Rephrasing Failure

**User Story:** As a newsletter operator, I want the pipeline to continue functioning even when the title-rephrasing LLM call fails, so that a single API error does not block newsletter generation.

#### Acceptance Criteria

1. IF the Groq_Client request for title rephrasing raises an exception, or returns an empty, whitespace-only, or unchanged (per Requirement 1, Criteria 5–6) title, THEN THE Title_Rephraser SHALL use a minimally cleaned version of the Original_Title as the Rephrased_Title without retrying the Groq_Client request.
2. WHEN the Title_Rephraser falls back to a minimally cleaned Original_Title, THE Title_Rephraser SHALL strip markdown and HTML markup from the Original_Title before storing it, and SHALL NOT otherwise truncate, reword, or modify the Original_Title text.
3. IF the Groq_Client request for title rephrasing fails for a given article, THEN THE NLP_Pipeline SHALL retain that article in the newsletter using the fallback title and SHALL continue processing that article's remaining enrichment steps (reading time estimation) and all other articles without interruption, and SHALL retain that article in the newsletter with the fallback title even if its remaining enrichment steps also fail.
4. IF the Groq_Client request for title rephrasing raises an exception, THEN THE Title_Rephraser SHALL still store the Original_Title in the Article_Record's `original_title` field.

### Requirement 4: Original Title Preservation

**User Story:** As a newsletter operator, I want the original publisher title retained on each processed article, so that I can inspect or audit the source headline for debugging purposes.

#### Acceptance Criteria

1. WHEN the NLP_Pipeline completes processing an article, whether the Title_Rephraser succeeded or fell back per Requirement 3, THE Article_Record SHALL contain both the `title` field holding the Rephrased_Title (or fallback title) and the `original_title` field holding the Original_Title, byte-for-byte unmodified from the value the Fetcher retrieved from the source.
2. THE Fetcher's deduplication logic SHALL continue to operate on each article's `title` field as retrieved from the source, before any rephrasing occurs, such that two articles sharing the same source title SHALL still be treated as duplicates regardless of any Rephrased_Title later generated for either one.

### Requirement 5: Newsletter Rendering of Rephrased Titles

**User Story:** As a newsletter subscriber, I want to see the rewritten headline in the newsletter I receive, so that the displayed content reflects the rephrasing rather than the original publisher wording.

#### Acceptance Criteria

1. WHEN the Newsletter_Template renders the newsletter, THE Newsletter_Template SHALL display each included Article_Record's `title` field value in that article's title element.
2. THE Newsletter_Template MAY display an Article_Record's `original_title` field value in addition to its `title` field value; if displayed, THE Newsletter_Template SHALL NOT present the `original_title` value as the article's primary title element in place of the `title` value.
