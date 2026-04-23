# KidsNews old schema design

**Date:** 2026-04-23
**Purpose:** Capture the current pre-redesign schema from the live Supabase project and reconcile it with the original code and repo documents.

## 1. Source of truth used here

This document is based on two inputs:

- live Supabase schema inspection through MCP against project `lfknsvavhiqrsasdfyrs`
- repo cross-checks from `CLEANUP.md` and `user_manager/user_manager_supabase.js`

This is the old schema that remains live while the redesign is introduced in parallel.

## 2. High-level shape

The live schema is not one single clean domain model. It is a layered system:

1. a content ingestion and article-processing model centered on `articles`
2. a legacy user/subscription model centered on `users`
3. a newer auth-backed profile flow centered on `user_profiles` and `magic_links`
4. some operational/config tables such as `feeds`, `categories`, `cron_jobs`, `api_keys`, and `secrets`

The redesign should treat the article-processing model and the newer auth-backed user model as the real compatibility surfaces.

## 3. Old content model

### Core lookup tables

#### `categories`

- rows: 7
- RLS: enabled
- primary key: `category_id`
- main columns:
  - `category_id`
  - `category_name`
  - `description`
  - `prompt_name`
  - `created_at`
- referenced by:
  - `articles.category_id`
  - `feeds.category_id`
  - `user_categories.category_id`

#### `feeds`

- rows: 10
- RLS: enabled
- primary key: `feed_id`
- main columns:
  - `feed_id`
  - `feed_name`
  - `feed_url`
  - `category_id`
  - `enable`
  - `created_at`
- relationship:
  - `feeds.category_id -> categories.category_id`

#### `difficulty_levels`

- rows: 3
- RLS: enabled
- primary key: `difficulty_id`
- main columns:
  - `difficulty_id`
  - `difficulty`
  - `meaning`
  - `grade`
- used by article enrichment tables and legacy preference tables

### Primary article table

#### `articles`

- rows: 895
- RLS: enabled
- primary key: `id`
- comment: `Main articles table storing news content`
- main columns:
  - `id`
  - `title`
  - `source`
  - `url`
  - `description`
  - `pub_date`
  - `content`
  - `crawled_at`
  - `deepseek_processed`
  - `deepseek_failed`
  - `deepseek_last_error`
  - `deepseek_in_progress`
  - `processed_at`
  - `category_id`
  - `zh_title`
  - `image_id`
  - `created_at`

Key observations:

- this is the old system's hub table
- it stores both source ingestion fields and processing state fields
- it already carries one localized field, `zh_title`, but not the redesign's full variant model
- it is category-based, but not aligned to the redesign parallel-table contract

### Attached article assets and derived content

#### `article_images`

- rows: 895
- RLS: enabled
- primary key: `image_id`
- main columns:
  - `image_id`
  - `article_id`
  - `image_name`
  - `original_url`
  - `local_location`
  - `small_location`
  - `new_url`
  - `created_at`
- relationship:
  - `article_images.article_id -> articles.id`

#### `response`

- rows: 864
- RLS: enabled
- primary key: `response_id`
- main columns:
  - `response_id`
  - `article_id`
  - `respons_file`
  - `payload_generated`
  - `payload_generated_at`
  - `payload_directory`
- relationship:
  - `response.article_id -> articles.id`

#### `article_analysis`

- rows: 0
- RLS: enabled
- primary key: `analysis_id`
- columns:
  - `analysis_id`
  - `article_id`
  - `difficulty_id`
  - `analysis_en`
  - `created_at`

#### `article_summaries`

- rows: 0
- RLS: enabled
- primary key: `id`
- columns:
  - `id`
  - `article_id`
  - `difficulty_id`
  - `summary`
  - `generated_at`

#### `keywords`

- rows: 0
- RLS: enabled
- primary key: `word_id`
- columns:
  - `word_id`
  - `word`
  - `article_id`
  - `difficulty_id`
  - `explanation`

#### `comments`

- rows: 0
- RLS: enabled
- primary key: `comment_id`
- columns:
  - `comment_id`
  - `article_id`
  - `difficulty_id`
  - `attitude`
  - `com_content`
  - `who_comment`
  - `comment_date`
  - `created_at`

#### `background_read`

- rows: 0
- RLS: enabled
- primary key: `background_read_id`
- columns:
  - `background_read_id`
  - `article_id`
  - `difficulty_id`
  - `background_text`
  - `created_at`

### Structural relationships in the old article model

The old article schema is strongly article-centric:

- `articles` is the parent object for payloads and enrichments
- `article_images`, `response`, `article_analysis`, `article_summaries`, `keywords`, `comments`, and `background_read` all hang off `articles.id`
- `difficulty_levels` is reused by multiple child tables instead of variants being first-class records

There is also a circular image reference:

- `article_images.article_id -> articles.id`
- `articles.image_id -> article_images.image_id`

This matches the cleanup logic already documented in `CLEANUP.md`, which explicitly notes that `articles.image_id` must be nulled before image rows are removed.

## 4. Old user model

### Legacy user tables

#### `users`

- rows: 0
- RLS: enabled
- primary key: `user_id`
- comment: `Legacy user system (deprecated)`
- main columns:
  - `user_id`
  - `email`
  - `token`
  - `password`
  - `username`
  - `first_name`
  - `last_name`
  - `registered`
  - `registered_date`
  - `created_at`
  - `updated_at`

#### `user_difficulty_levels`

- rows: 0
- RLS: enabled
- foreign keys:
  - `user_id -> users.user_id`
  - `difficulty_id -> difficulty_levels.difficulty_id`

#### `user_categories`

- rows: 0
- RLS: enabled
- foreign keys:
  - `user_id -> users.user_id`
  - `category_id -> categories.category_id`

#### `user_preferences`

- rows: 0
- RLS: enabled
- main columns:
  - `email_enabled`
  - `email_frequency`
  - `subscription_status`
  - `updated_at`
- relationship:
  - `user_preferences.user_id -> users.user_id`

This legacy branch is still present in schema, but the live app appears to have moved away from it.

### Newer auth-backed user tables

#### `user_profiles`

- rows: 2
- RLS: disabled
- primary key: `id`
- relationship:
  - `user_profiles.id -> auth.users.id`
- main columns:
  - `id`
  - `email`
  - `display_name`
  - `preferences` JSONB
  - `role`
  - `created_at`
  - `updated_at`

#### `magic_links`

- rows: 5
- RLS: enabled
- primary key: `token`
- main columns:
  - `token`
  - `email`
  - `reading_style`
  - `expires_at`
  - `created_at`

#### `user_stats`

- rows: 1
- RLS: enabled
- primary key: `id`
- relationship:
  - `user_stats.user_id -> auth.users.id`
- main columns:
  - `id`
  - `user_id`
  - `stats` JSONB
  - `synced_at`
  - `created_at`

#### `user_subscriptions`

- rows: 0
- RLS: enabled
- primary key: `user_id`
- comment: `User subscription management (new system)`
- main columns:
  - `user_id`
  - `email`
  - `name`
  - `reading_style`
  - `bootstrap_token`
  - `bootstrap_failed`
  - `subscription_status`
  - `verified`
  - `device_id`
  - `created_at`
  - `updated_at`

#### `user_progress`

- rows: 40
- RLS: enabled
- main relationship:
  - `user_progress.word_id -> words.id`

## 5. Repo cross-check against the live schema

### `CLEANUP.md`

The cleanup document matches the live article-centered design:

- parent table: `articles`
- child tables: `response`, `article_images`, `article_analysis`, `article_summaries`, `keywords`, `comments`, `background_read`
- special handling for the `articles.image_id` circular reference

This confirms that the live schema and the maintenance scripts still treat `articles` as the old production center.

### `user_manager/user_manager_supabase.js`

The current Supabase-backed user flow is wired to the newer auth-backed tables, not to the deprecated `users` tree.

Observed live-facing tables in code:

- `magic_links`
- `user_profiles`

Observed behavior in code:

- reads a pending `reading_style` from `magic_links`
- deletes consumed `magic_links` rows after successful use
- fetches or upserts `user_profiles`
- stores reading-style preferences inside `user_profiles.preferences`

That means the old user area is already a hybrid system: the deprecated `users` tables still exist, but the browser-side auth flow is using `auth.users + user_profiles + magic_links`.

## 6. Design conclusions for the redesign

The old schema has three important limitations that justify the redesign parallel-table rollout:

1. `articles` mixes ingestion state, publishable story state, and localized content in one table.
2. difficulty-specific outputs are scattered across multiple child tables instead of being normalized as story variants.
3. the user area is split between deprecated legacy tables and newer auth-backed tables.

This is why the redesign should continue to:

- keep the old schema live for compatibility
- write redesign pipeline output into the new parallel table family first
- avoid expanding the old `articles` tree with more redesign-specific fields
- preserve compatibility with the current auth-backed user flow instead of reviving the deprecated `users` model

## 7. Minimal compatibility surfaces to remember

If the redesign needs temporary adapters before final cutover, the likely compatibility surfaces are:

- article listing and archive publishing derived from the old `articles` pipeline outputs
- image linkage currently expressed through `articles.image_id` and `article_images`
- payload directory tracking currently stored in `response`
- login and reading-style flow currently tied to `user_profiles` and `magic_links`

These are the places where migration glue, views, or copy jobs will matter most.