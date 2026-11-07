# Developer B integration status

**Base:** `origin/main` at `2d62371410cc5721e112a46e95e17ec8760fdc21`  
**Branch:** `integration/b-web`  
**Date:** 2026-11-07

This is an evidence log for the B consumer side. It intentionally separates
library/demo checks from live A HTTP/WS acceptance. No item below is called
release-ready without a deployed backend and persisted state evidence.

## Current matrix

| Area | Current state | Evidence / blocker |
|---|---|---|
| Generated A client | Connected in repository; `contracts/generated/api.d.ts` is the source of DTO types | B must remove remaining temporary API types and use one adapter |
| Same-origin HTTP client | Consumer boundary implemented | B `ApiClient` uses same-origin credentials, timeout/AbortController, CSRF cookie provider and stable caller-supplied idempotency keys; generated DTO aliases are consumed by game/AI clients |
| Auth/session | Partial | UI now targets `/api/v1/me` and `/api/v1/logout`; production fake auth is rejected. Real OIDC/dev session and CSRF handshake remain A-dependent |
| Solo/AI/Coach game | Demo/mock boundary | A release preflight reports missing game routes; no live move/Stockfish evidence |
| Coach | B provider/grounding tests pass; runtime route absent | A-015/A-011/A-014 composition, queue and AnalysisReader required |
| Learning | Schemas and demo adapters exist | Real lesson/puzzle/progress routes and persistence are absent |
| Friend/rated | UI screens and mock snapshot board exist | Invitation/matchmaking/game HTTP and WS routes are absent |
| WebSocket | Client boundary/unit tests exist | Client accepts only generated `GameEventV1` event types; `/ws/v1/games/{game_id}` is missing from composed app and needs runtime evidence |
| E2E | Navigation/demo smoke only | Existing Playwright tests do not call A backend or verify DB/WS state |
| Release preflight | Blocked | `python -m infra.release_check` exits 1: 18 HTTP operations and game WS missing |

## Checks run on this base

- `python -m infra.release_check` — **FAIL (expected blocker)**; see `docs/A027_RELEASE_STATUS.md`.
- `pnpm run lint` — **PASS**.
- `pnpm run typecheck` — **PASS**.
- `pnpm run test` — **PASS (43 tests)**.
- `pnpm run build` — **PASS**.
- `pnpm run test:e2e:live` — **FAIL by design without `MLCHESS_LIVE_BASE_URL`**; it refuses to run demo tests when no live backend is configured.
- Live HTTP/WS and two-browser tests — **NOT RUN**; required A routes are not composed.

## B next steps

1. Replace remaining legacy feature API paths with published generated contracts once A merges them.
2. Confirm CSRF cookie/header handshake and add live mutation evidence.
3. Update auth consumer to `/api/v1/me` and `/api/v1/logout`; keep fake auth dev-only.
4. Add live E2E command/fixtures that fail clearly when `MLCHESS_LIVE_BASE_URL` is absent.
5. Refresh this file with exact runtime SHA and HTTP/WS/DB evidence after A publishes the missing surface.

## Requests to A

- Publish the deployed API/WS base URL and exact contract SHA used by staging.
- Mount game, coach and learning routers with session/ACL/mode guards.
- Provide the CSRF handshake/header contract for browser mutations.
- Provide a disposable PostgreSQL/Redis/worker/Stockfish staging profile for `test:e2e:live`.
