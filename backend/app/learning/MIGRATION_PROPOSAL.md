# Learning persistence proposal (B-002/B-020/B-022)

This is a proposal for A's Alembic owner; B does not create or register a migration.

## Tables

- `lessons`: `id` primary key, `schema_version`, localized content, provenance URL/license, `created_at`.
- `puzzles`: `id` primary key, FEN, difficulty, tags, provenance URL/license, `solution_digest` (never the solution line in API responses).
- `puzzle_attempts`: `id` primary key, `student_id`, `puzzle_id`, `idempotency_key`, result, next ply, created_at. Unique `(student_id, idempotency_key)`.
- `student_skills`: `student_id`, `skill`, attempts/correct/hints/streak/due_at, primary key `(student_id, skill)`.
- `progress_events`: `student_id`, `event_id`, skill, result, created_at. Primary key `(student_id, event_id)`.

## Transaction boundary

Puzzle grading and progress event insertion must commit atomically. Replayed requests return the original attempt/progress snapshot without incrementing counters.

## Deletion/export

Account deletion removes attempts, progress events and student skills. Lesson/puzzle content remains only if it is curated public content and contains no user identity.

## Rollback

Drop the learning tables in reverse dependency order after a backup. No production migration should be merged until A validates indexes and PostgreSQL constraints against the deployed schema.
