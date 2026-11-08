# CCR-B-05 — Coach factory and port boundary

## Scope

B owns provider-neutral coach validation, grounding, fallback and the route
factory. A owns concrete principal/session ACL, verified analysis reads, durable
job storage, queue/worker execution and the application composition root.

The proposed B-facing ports are in `backend/app/coach/ports.py`:

- `PrincipalAccessGuard` — actor/game/mode/phase authorization;
- `VerifiedAnalysisReader` — returns facts only for the requested game,
  `analysis_id`, `ply` and `revision`;
- `CoachJobsPort` — durable idempotent lookup/create/get/save;
- `QueueEnqueue` — bounded enqueue, with no provider secret in the browser.

## Required A contract

Before production mounting, A must provide an `A-CONTRACT-READY` SHA containing
the concrete adapters, negative ACL cases and a working SQL-backed example. The
guard must reject active friend/rated games, foreign games and stale revisions.
The reader must never accept client-supplied FEN/PGN as authoritative facts.

## Job identity and persistence

The unique request key remains:

`(game_id, analysis_id, ply, revision, student_context_version, model_id, prompt_version, language, level)`

Duplicate requests return the original job. A GET reads persisted state only and
never invokes an LLM. Provider failures are bounded and represented by the
versioned job error code; deterministic fallback remains available.

This CCR does not add routes, migrations or alter A-owned files.
