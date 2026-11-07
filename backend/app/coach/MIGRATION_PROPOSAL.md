# `coach_explanations` migration proposal

This is a B-owned proposal for A. It is not an Alembic revision and must not be
run directly. A should merge it into the single migration head after the backend
DB connection and common UUID/FK conventions are available.

## Required constraints

- `analysis_id`, `game_id`, `revision`, `ply`, `model_id`, `prompt_version`, `language`, `level`, and `status` are required.
- `status` is one of `pending`, `ready`, `failed`.
- `fallback_used` is non-null and defaults to false.
- `error_code` is required only for failed jobs; `payload_json` is required only for ready jobs.
- Unique request key: `(analysis_id, model_id, prompt_version, language, level, student_context_version)`.
- The implementation must add the A-owned foreign keys and indexes for `analysis_id`/`game_id`.

## Rollback

Drop the table and its indexes in the reverse order of creation. No existing A-owned
tables should be altered by this proposal.
