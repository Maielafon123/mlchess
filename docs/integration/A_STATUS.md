# Developer A integration status

LATEST USER CONSTRAINT (2026-11-09): no VPN inspection/checksums/tests or changes.
Do not touch VPN files/interfaces/routes/rules/services. Current agent choice is
host networking to avoid bridge/NAT changes during recovery; this is a precaution,
not an established cause of the outage or an extra instruction from the user.
Use compose.vps-host.yml with the server base; private services bind loopback.
This supersedes older VPN-checklist text.

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

## Resume 2026-11-09

User reports loss of VPN connectivity during prior deployment and explicitly
forbids further VPN access/checks. No cause is inferred. The recovery deployment
avoids VPN checks and host-network changes by agent choice. Previously loaded application
images845f4b1 are present; application containers were not started.

Fetched Andrei integration/b-next at9ea5331 and merged his three commits: coach
protocols, learning handoff and refreshed B status. Coach/learning49 PASS; ruff
check/format PASS. These are integration interfaces, not new live endpoints.

Added host-network VPS overlay: zero Docker networks/port publishing/NAT/sysctls,
loopback-only data/API/static listeners, public-IP-only gateway. Rendered Compose
regression PASS without a Docker daemon. Local Docker Desktop is stopped; new
runtime acceptance/build/export is delegated to the existing GitHub Actions
workflow (not a separate agent). Host runtime guest acceptance is required before
public startup. The old standalone server bridge config is NOT used on this VPS.

## Public guest deployment accepted (2026-11-09)

PR37 merged at28d750024ca0aa8df0f40aed2956b1ffe554a41e; exact merge run42524839016
and all six PR jobs in42524465131 PASS. Host overlay acceptance includes six
Android Chromium/iPhone WebKit guest cases with development authentication OFF.
VPS runs existing application images845f4b149e946b68bf7e81ad306ed2ad855cd9af
with infrastructure7b3c81c670faac8fab1102e136f18bd61ea10110. The only application
source difference is the unused B coach port definitions. Do not confuse the
infrastructure revision with the deployed application image revision.

Public IP HTTPS uses a trusted Let's Encrypt certificate; HTTP redirects to HTTPS.
Ready200; six long-running services started, API/worker/web/data healthy, migrate0.
External phone acceptance on the actual public HTTPS address:6 PASS (19.8s).
Manual browser: guest AI creation, e2e4/e7e5, refresh restores same game/history;
390px mobile layout inspected. No certificate validation bypass. No VPN operations.
An inaccurate VPS clock was corrected using the existing synchronized chrony
source; neither network configuration nor VPN was inspected or changed.

Guest/mobile deployment is accepted. Full product signoff remains BLOCKED by
analysis, coach, learning, realtime, matchmaking and recovery tasks listed above.
Continue A-I09 durable analysis next.

## A-I09 analysis implementation

Mounted strict v1 request/result endpoints over existing analyses/worker/outbox
tables; no schema expansion needed. Actor/game locks, exact receipts, cache by
position/revision/policy/level, durable40jobs/hour quota and global256 pending cap.
No engine runs in HTTP. A separate bounded analysis-worker uses the shared SQL
lease mechanism, retries3, restart recovery and late-result fencing. Result and
analysis.ready event commit atomically. Active PvP is denied on submit/read/commit;
finished friendly participants can read verified analysis. Undo invalidates old
jobs even when a later line recreates the same ply. Advancement on the same line
does not invalidate an earlier analysis.

Stockfish15.1-4 binary pinned. Build exports the embedded NNUE using the upstream
export_net command, hashes the actual bytes, then removes the temporary export;
runtime verifies the build manifest against the running engine. Mate stays a mate
score; loss is calculated from mover POV only for cp. Facts include independently
checked en-passant capture square, promotion material gain, castling and checkmate.

Local: full backend487 PASS/17 SKIP before the last two added boundary tests;
final analysis26 PASS; engine/infra target previously36 PASS plus the corrected
invitation fixture case. Ruff check/format, web lint/build and generation check PASS.
PostgreSQL concurrency and real-container E2E are pending CI; no A-I09 live signoff
or deployment of these new analysis sources is claimed yet.

## A-I09 public runtime evidence and probe repair

PR38 merged c7fcb2bac57d559436826b6b0ea96edbba6cfbfc after all six jobs PASS
on head0597c93446dc402c4a795f9479f95801eeaa3aeb in42526640621. PostgreSQL
concurrent requests share one job/lease; gameplay advancement preserves earlier
analysis, unique event sequence and duplicate-delivery fencing PASS.
VPS API/gameplay/analysis images0597c93 deployed with infra c7fcb2b; static web and
gateway retain845f4b1 (no frontend/proxy change in this release). Pre-update SQL
backup retained with private server permissions. Public HTTPS Playwright7 PASS
(15.4s), including actual Linux Stockfish analysis, factual model/binary metadata,
result persistence across page reload and all six phone cases.

Runtime found an operational defect missed by CI: the analysis worker at0.4CPU
executes jobs but its ORM-heavy health subprocess exceeds the5s probe timeout on
this VPS. No OOM/restarts occurred. Replace repeated ORM/app imports with a small
asyncpg probe, connect/query/close timeouts2/2/1s, no exception output. Host overlay
mounts that probe read-only so an unchanged tested application image can receive
the correction. Targeted probe/host config4 PASS; actual VPS measurement pending.

Probe correction PR39 merged0a143bdf7e558419e5a38a750fe932b012ad6e4c after six
green PR jobs42527615370. Exact merge CI42527893564 PASS; analysis merge
CI42526905637 PASS. Actual lightweight VPS probe3.42s; updated host overlay deployed
with existing0597c93 API/worker images. All six application/data health checks PASS,
including the previously unhealthy analysis-worker. No VPN access or checks.

## A-I10 coach composition implementation (CI pending)

CCR-A-I10-COACH records the cross-owner integration and tighter principal privacy.
Expand-only0004 persists explanations, foreign keys and request uniqueness. The
guarded B router mounts only game-scoped async endpoints; both reads and writes
recheck the actor, game phase, completed analysis and current revision. A separate
coach-worker executes B CoachService and grounding in a bounded child process,
with8s hard timeout,32KiB input/output and no database credentials in its environment.
Provider failures become deterministic fallback; stale results cannot publish.

No cloud model credentials are available. Production provider verified-rules-v1
is explicit rule-based feedback from actual engine facts, not fake and not an LLM.
External LLM validation remains pending credentials; no full LLM signoff is claimed.
The child and parent repeat grounding; ready payload and coach.ready event commit
atomically. Personalized jobs/caches remain private even from the other player.

Frontend uses generated analysis/coach types, reconstructs legal PV previews,
keeps White POV, resumes the coach game URL, requests analysis only for the human
move and hides old hints immediately on branch/context change. Five hint levels
are localized; Android Chromium/iPhone WebKit live coach cases added to CI.

Local: full backend499 PASS/17 SKIP before the final same-game privacy test;
final durable coach5 PASS, earlier coach/host target52 PASS. Web51 unit PASS;
stale-analysis/hint tests3 PASS; build/lint and demo3 PASS. Contract44 fixtures and
generation64 tests PASS, including a Windows CRLF checkout without false drift.
Surface preflight still BLOCKED: five learning/matchmaking HTTP operations and WS.
Next: real PostgreSQL/Compose coach acceptance, then persistent learning.
