# Developer A integration status

Baseline origin/main: `8095e86882187441842048cab2db9f2cfb657bcb`.
Worktree `a-backend`, branch `integration/a-backend`.
User-provided CODEX_DEVELOPER_A.md read completely.

## Evidence

- PR #32: durable sessions and eight game HTTP operations merged.
- PR #33: bounded independent engine worker, durable leases/fencing merged.
- Merge-SHA CI PASS: https://github.com/Maielafon123/mlchess/actions/runs/42410515662
- Full backend with disposable PostgreSQL: 456 PASS, 2 Windows SKIP; subsequent
  recovery-dialect regression: 1 PASS. Targeted engine/HTTP/PG suite: 26 PASS.
- Worker subprocess/API restart, duplicate apply, expired lease, last-attempt
  crash, takeback stale reply: 7 worker tests PASS.
- Pinned real Stockfish: legal move and three legal scored PVs PASS.
- Alembic 0003 and isolated pg_dump/restore PASS. Production RPO/RTO unverified.
- Route preflight FAIL: 10 required HTTP operations and game WebSocket absent.

## Blockers and ordered work

1. A-I00: save baseline route JSON. A-I01: compose proxy/web/API/worker,
   migrations, PostgreSQL and Redis under one origin, then real browser smoke.
2. A-I02: generated DTO/CSRF handoff; B PR #31 is a partial consumer update.
   B owns apps/web, coach/learning code and their contracts. A owns adapters,
   domain/storage/infra/generation; record CCRs before changing public wires.
3. A-I03-I08 server slice implemented; browser acceptance still required.
4. A-I09: analysis jobs/results. A-I10: guarded durable coach composition.
   A-I11: learning migrations and persistent server ports (B domain/router).
5. A-I12-I15: WebSocket, invitations, scheduler, matchmaking/rating HTTP wiring.
6. A-I16: Google OIDC selected by user; credentials/domain unavailable. Complete
   body/rate/resource limits and negative security tests. Never fake prod auth.
7. A-I17-I19: merge-SHA CI, live four-mode/learning E2E, recovery/offsite/PITR,
   license/SBOM checks and signoff. Production/public release remains BLOCKED.
8. User requested full refactor and microservices AFTER the document's
   integration tasks. Write an ADR before changing the later service target.
   Preserve protected legacy code until the explicitly requested refactor phase.

## Deployment constraints and handoff

User-provided VPS key access verified read-only: Ubuntu 26.04, Docker 29.1.3,
Compose 2.40.3, 2 CPUs, about 3.8 GiB RAM. Existing WireGuard is protected:
do not change VPN files, routing, sysctls, firewall policy or restart networking.
Keep actual server/network/access details and secrets out of tracked artifacts.
Choose non-overlapping app networks and bound container CPU/RAM.

CreateGameV1 requires explicit time_control and solo human_color/ai_profile.
Moves return MoveAcceptedV1.snapshot. Takeback requires plies/client_action_id.
Readable mlchess_csrf cookie maps to X-CSRF-Token. Session cookie is HttpOnly,
path=/, SameSite=Lax, Secure with HTTPS. Login rotates opaque tokens; logout
revokes durable sessions; every private operation requires participant ACL.

## A-I00/A-I01/A-I02 live integration (2026-11-08)

Integrated B #31 at 820f6b5. CCR-A-I02-CONSUMER documents bounded consumer
repairs without changing v1: browser fetch binding, problem+json, empty204,
body-read deadline/cancellation, real dev sessions, profile IDs, fenced worker
polling, takeback and StrictMode idempotent create. Live/demo artifacts are
separate and excluded from Git/Docker (they may contain disposable cookies).

PASS: pinned Docker build (Linux Stockfish15.1-4 hash checked), Compose
up --wait, Alembic0001-0003, six long-running services healthy, migrate exit0.
Only gateway loopback8080 is published; data services have no host ports.
PASS: pnpm test 47; build; lint. Demo Playwright3 PASS; real Compose Playwright2
PASS (two distinct SQL users, ACL403, engine response, takeback, logout401).
Backend: 465 PASS/2 Windows SKIP plus one setup failure caused by absent
contracts/node_modules in the new worktree; npm ci installed missing tooling
and the affected generator test is rerun separately. Ruff check/format PASS.
Affected generator test PASS after npm ci; generated check/SDK typecheck/tests
PASS. PR #34 merged at b9d51c719cf4be5f201a82292f5c32e83175ca5b; all five CI
jobs PASS, including live-compose run42413995948.
No production/VPS deployment claimed by these local checks.

## User priority update

User now prioritizes mobile browser access by tomorrow and a private challenge
link that works without login. Implement guest sessions + durable single-use
invites, mobile layout and real two-phone/browser acceptance before resuming
analysis/coach/learning/refactor tasks. Previous account-only friend policy is
explicitly superseded by this request; document CCR and preserve rated-account
restrictions. Public deployment must disable dev auth, use static web + TLS,
SQL persistence, request/resource limits and preserve protected WireGuard.
User confirmed NO domain: use the supplied public IP with a publicly trusted
certificate. Google OAuth must not block anonymous friendly games.

## A-I13 guest/mobile implementation

CCR-A-I13-GUEST-CHALLENGE records the explicit policy change. SQL guest sessions,
24h single-use invitations, exact replay without raw tokens in receipts, locked
join, server event and browser-seat restoration implemented. Guest session7days.
Guest route is real session issuance; dev login remains disabled in server config.
Limiter/body/resource bounds added. Rated and active-PvP coaching/undo stay denied.

Local evidence: full backend478 PASS/2 Windows SKIP; subsequent guest/settings
target17 PASS. PostgreSQL concurrent-accept regression1 PASS. Schemas41 golden
examples, generator and structural compatibility PASS; SDK typecheck/2tests PASS.
Web48 unit PASS including the worker/takeback UI race regression.
Build/lint/demo3 PASS; static Compose live8 PASS including Android Chromium and
iPhone WebKit touch, two guest users, third-user rejection, refresh, AI black side
and takeback. Mobile screenshots inspected;320px layout has no horizontal overflow.

Production Compose/static gateway/images and server initializer implemented;
Caddy config validated locally. Public TLS/VPS acceptance and exact merge CI
remain pending. No all-mode production signoff is implied by guest/mobile checks.

Next smallest task: guest challenge links + mobile public deployment.
