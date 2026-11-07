# Developer B corrective sprint status

## Implemented in this branch

- B-FIX-01: CoachJob payload parity, game-scoped route aliases, explicit access guard, and GET read-only behavior.
- B-FIX-06: bounded typed provider prompt, metadata identity checks, provider fail-closed fallback.
- B-FIX-07: coach polling now uses bounded exponential backoff, full request identity, terminal timeout, and cancellation by request generation.
- B-FIX-08: completed puzzle attempts are terminal; duplicate progress events are idempotent.
- B-FIX-09 (B-owned portion): client endpoint/header corrections and honest demo-state labeling.
- B-FIX-09 (continued): friend/rated screens render server snapshots and submit moves through `GameApi`; PvP screens still expose no coach/analysis controls.
- Learning demo adapters are now explicit (`LearningApi.demo()`, `PuzzleApi.demo()`, `ProgressApi.demo()`); real clients use `/api/v1/learning/*`.
- B-002 foundation: learning schemas, router boundary, and migration proposal for A's Alembic owner.
- B-023 provenance guard: generated exercises require finished, server-verified analysis provenance.

## Not claimed as complete

- A-owned auth/session, game state, AnalysisReader, queue workers, migrations, WebSocket, engine and router composition are still required.
- Friend/rated two-browser acceptance cannot be signed off until A staging is available.
- Learning progress and lessons remain demo-backed in the UI until A mounts the learning router and persistence.

## Required A follow-up

See `docs/CCR-B-FIX-01.md`. Production must mount only the guarded game-scoped coach routes and supply durable queue/storage dependencies.
