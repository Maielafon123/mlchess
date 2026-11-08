# Developer B integration status

**Base:** `origin/main` at `845f4b149e946b68bf7e81ad306ed2ad855cd9af`  
**Branch:** `integration/b-next`  
**Date:** 2026-11-09

This is the current B consumer/domain evidence log. Demo UI checks and live
Compose checks are separate; no production or public VPS sign-off is claimed.

A integration update: public guest/mobile and analysis are now verified on the
IP HTTPS deployment (PR38/c7fcb2b, external7 cases PASS). Host probe fix PR39
merged0a143bd and all app/data health checks PASS. The baseline table below is
the earlier B handoff, not the current deployed analysis state. A-I10 coach SQL,
guarded router, worker and generated consumers are implemented under
CCR-A-I10-COACH; runtime acceptance is pending CI. No cloud LLM is configured;
verified-rules-v1 identifies actual rule-based coaching from engine facts.

## B-00 baseline map

| Area | Current state | Evidence / blocker |
|---|---|---|
| Guest sessions/challenge | Live in local Compose | PR #35: durable guest session, single-use invite, seat restore and third-user rejection; public TLS/VPS not verified |
| Solo AI | Live in local Compose | Real PostgreSQL command path, Stockfish worker response and takeback covered by A live scenarios |
| Friend | Live in local Compose over HTTP polling | Guest two-browser/mobile flow passes; real game WebSocket is still absent |
| Rated | UI boundary only | Account/OIDC and matchmaking API are not composed; guest rated remains denied |
| Analysis | Server primitives exist, consumer still temporary | `apps/web/src/api/analysis.ts` uses legacy types; analysis routes are missing from composed app |
| Coach | B provider, grounding and pure service tests exist | Production router is intentionally empty; durable A ports, queue, ACL and persistence are required |
| Learning | B pure services and demo adapters exist | Production router is empty; lessons, puzzle attempts and progress routes are absent |
| WebSocket | Client boundary and tests exist | `/ws/v1/games/{game_id}` is missing; live resync/reconnect evidence unavailable |
| Mobile | Live static Compose scenarios pass | Android Chromium and iPhone WebKit pass at 320px; public deployment remains unverified |

## Checks executed on this base

- `pnpm --dir apps/web run lint` — **PASS**.
- `pnpm --dir apps/web run typecheck` — **PASS**.
- `pnpm --dir apps/web run test` — **PASS (48 tests)**.
- `pnpm --dir apps/web run build` — **PASS**.
- `pnpm --dir apps/web run test:e2e` — **PASS (3 demo scenarios)**.
- `python -m infra.release_check` — **BLOCKED**: 8 HTTP operations and
  `/ws/v1/games/{game_id}` are not mounted.
- A reports backend **478 PASS / 2 Windows SKIP**, static Compose **8 live
  scenarios PASS** and generated contract checks PASS in `A_STATUS.md`.

## Current B-owned blockers

1. A analysis contract/handler must become `A-CONTRACT-READY` before B replaces
   the temporary analysis consumer and wires coach context to a real `analysis_id`.
2. A coach ports (verified analysis reader, principal/ACL, queue and durable
   store) are required before mounting guarded coach routes.
3. A learning migrations/store ports are required before live lesson, puzzle and
   progress routes can replace `.demo()` adapters.
4. A realtime WebSocket route is required before friend UX can move off polling.
5. Public TLS/VPS deployment, OIDC credentials and cloud LLM credentials remain
   explicitly unverified or blocked.

## Next B work

- B-02/B-03: freeze generated analysis consumer after A contract handoff;
- B-05/B-06: publish coach factory/port CCR and guarded route factory on fake
  ports, without claiming production routes;
- B-11/B-14: finish learning contract/port proposals and persistence handoff;
- B-18/B-19: integrate `GameWebSocket` after A mounts the real route.

## Latest B-05/B-11 handoff

- Commit: `6d3b59e` (`integration/b-next`).
- Added provider-neutral coach ports in `backend/app/coach/ports.py` without
  changing A-owned composition or creating migrations.
- Added `CCR-B-05-COACH-PORTS.md` and `CCR-B-11-LEARNING-CONTRACT.md` with the
  required ACL, idempotency, storage and `A-CONTRACT-READY` handoff conditions.
- `python -m pytest backend/tests/coach backend/tests/learning -q` — **PASS
  (49 tests)**.
- `ruff` was not installed in this Windows environment; no ruff result is
  claimed for this commit.

Every ticket must record its exact base SHA, B-owned files, tests, live-vs-mock
evidence, security negatives, open CCRs and handoff requirements.
