# CCR-B-FIX-01 — Coach and learning integration boundary

## Consumer

Developer B coach UI and learning services.

## Existing boundary

Coach currently exposes a B-owned router factory and deterministic in-memory service. The factory does not register itself in the A application composition.

## Requested A integration

- Mount the B router only behind the authenticated session dependency.
- Provide an `AnalysisReader` port that returns server-owned `AnalysisFacts` for `(user, game_id, analysis_id, revision, ply)`.
- Reject `friend` and `rated` modes and foreign game IDs with `403`.
- Enqueue coach jobs on the `coach` queue; `GET` must only read durable state and never invoke the provider.
- Persist job lifecycle and enforce unique idempotency for request creation.
- Mount the game-scoped routes:
  - `POST /api/v1/games/{game_id}/coach-requests`
  - `GET /api/v1/games/{game_id}/coach-requests/{job_id}`

## Compatibility

The request/job payload remains schema version 1. The B router retains the legacy unscoped routes only for deterministic mock fixtures; production composition should mount the game-scoped routes.

## Golden tests requested from A

1. anonymous and foreign users receive `401/403`;
2. active friend/rated games receive `403`;
3. own coach request returns `202` and later `200 ready`;
4. GET never calls the LLM provider;
5. stale analysis revision produces deterministic fallback and no publish;
6. duplicate `Idempotency-Key` returns the original job.

## Blocked tickets

B-013, B-014, B-015, B-023, B-025.
