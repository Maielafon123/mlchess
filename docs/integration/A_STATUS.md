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

## A-I10 live acceptance and concurrent-read correction

PR40 mergedcad3c5808598b81c84780c1067dc8404c3783b7f after all six jobs PASS
in42529744334 on45addbc0163c65845e61bf6256bea6c15cbd9fee. Earlier ae8f907
failed the Docker frontend build because test JSON fixtures were not copied into
the build stage;45addbc fixes the missing input without changing test coverage.
All four application images45addbc deployed; migration0004 completed, gateway and
seven app/data containers started, all available health checks PASS. Private
pre-coach SQL backup retained. Browser manually verified e2e4, engine reply and
both observation/solution hints without fallback; mobile screenshot retained locally.

Public concurrent Playwright on the VPS found8 PASS/2 FAIL. One WebKit coach case
received analysis STALE_POSITION while the persisted game remained active, same
revision0, advancing version1->2. Root cause: worker preflight reads did not lock
the game while loading the separate state row; a gameplay commit could mix two
READ COMMITTED snapshots. HTTP game/result reads were already locked. Analysis
and coach position capture now take the same short game lock; no inference/provider
runs under that lock. A real PostgreSQL gated-read/write regression is added.

The second WebKit error happened37ms into page reload, with surrounding game HTTP
requests all200: an in-flight poll was cancelled by navigation. ApiClient now aborts
explicitly at pagehide and removes the lifecycle listener after completion.
Transport cancellation is unit-tested; repeated public WebKit acceptance pending.
Explicit new analysis commands can retry a failed/stale current position under the
same40/hour and256 pending limits; old receipts remain exact. Retry events count
toward the quota. Undo/current phase/ACL checks remain mandatory before retry.

Learning work was preserved on codex/durable-learning and has now been restored (no remaining stash):
eight original bilingual lessons, four mechanically validated mate puzzles and
one expand-only0005 schema/seed migration (offline and fresh SQLite upgrade PASS).
No learning routes or production learning deployment are claimed yet.

Coherent-read correction PR41 mergedb45791b6365cf23595b895243a1c045a4706a508
after six green jobs42531660756 on6baf166ef447eaee627b0e535c6b72fcaa79eacd.
All four images6baf166 deployed with matching infrastructure; migration/health PASS.
Repeated external public HTTPS acceptance:10/10 PASS in30.5s at6 workers, including
all three coach browsers, held-poll reload on iPhone/Android and all guest flows.
The gated PostgreSQL concurrent capture regression PASS. A separate old-release
WebKit held-poll control also passed, so the original navigation failure was
intermittent; the cancellation change is defensive and the public retest is green.
Proceed with A-I11; no full-product or external-LLM signoff is implied.


## A-I11 persistent learning implementation (acceptance pending)

Base b45791b6365cf23595b895243a1c045a4706a508, exact-main CI42532285064 PASS;
coach merge cad3 exact-main CI42530143824 PASS. Andrei integration/b-next remains
9ea5331, already integrated. Cross-owner work follows CCR-A-I11-LEARNING.md.

Migration0005 adds nine learning tables and a frozen original CC BY4.0 seed:
eight bilingual lessons and four mechanically legal mate-in-one puzzles.
All14 guarded learning routes now use SQL. Actor row locks serialize commands,
receipts preserve exact responses, attempt identifiers deduplicate progress, cursor
and restart counters reject old tabs. A retained learning epoch also fences delayed
pre-reset commands. Reset removes only this actor's learning, retaining games/auth.
The grader accepts equivalent final mates, including rook underpromotion. Private
solutions never appear in initial DTOs or the production frontend bundle; hints
are server requests and replay appears only after completion. Progress follows
server grades and hint events, with spaced review dates and paginated private export.

Frontend now uses generated DTOs and live HTTP throughout lessons, puzzles and
progress. Removed bundled demo solutions, fabricated metrics and localStorage
lesson persistence. Added RU/EN learning navigation, mobile selection/replay,
explicit reset UI and stable command retries after uncertain transport outcomes.
Demo E2E fixture transport exists only in the test source; live tests use real SQL.

Local full backend524 PASS/19 SKIP before final migration/export additions;
learning+migration/recovery target24 PASS before final export negatives. Web53
unit PASS, demo3 PASS, production build and lint PASS. Contracts49 goldens PASS,
generation current. PG races and all three live learning browsers added to CI;
no PostgreSQL or public learning success is claimed until those jobs execute.
Route preflight still blocks on two matchmaking operations and WebSocket transport.
External Google/LLM credentials and offsite PITR acceptance remain outstanding.


A-I11 first CI run42535352848: contracts, legacy, web and real PostgreSQL recovery/
learning races PASS. Live Compose found a true320px horizontal overflow in the
new learning action/navigation rows; grading, hint persistence and lesson flows
passed before the layout assertion. Corrected action wrapping and added a local
320px browser regression; demo3 PASS. Final local learning target28 PASS. Public
learning is not deployed while either Compose acceptance remains red.


## A-I11 public acceptance

PR42 merged fdad44bf5329b03cc1441ac9f2878aef681a4a31 after all six jobs PASS in
42535741410 on02943b3d550041a2f7879fde56ddef68313984b9. Exact merge CI42536048721
also PASS. Both real PostgreSQL learning races PASS. All four tested images02943b3
deployed with matching infrastructure;0005 migration and all health checks PASS.
Pre-learning private application pg_dump retained; no host/VPN networking touched.

Public trusted HTTPS acceptance13/13 PASS in32.9s at6 workers: desktop, Android
Chromium and iPhone WebKit learning/hints/completion/progress/reload; existing
friend/two-phone/AI/coach/analysis cases stay green. Manual browser additionally
accepted f7f8r as an alternative mate and retained that exact solution on refresh.
Public learning screenshots retained locally. No full release tag created.
Proceed with A-I12; matchmaking, clock scheduler, Google/remote LLM and offsite
PITR remain separate work, not implied by this acceptance.


## A-I12 durable read-only WebSocket implementation (CI acceptance pending)

Base fdad44bf5329b03cc1441ac9f2878aef681a4a31. WS `/ws/v1/games/{game_id}` is
mounted behind mandatory Origin, actual opaque session and participant guards.
A fresh snapshot/cursor pair is captured under the game lock; subsequent SQL
batches replay/tail the same durable log, without a volatile handoff or invented
Redis delivery claim. Every batch reauthorizes; private/stale/PvP result references
cause safe resync instead of leaking identifiers or skipping a sequence.

Admission32 per process/4 per actor, bounded reads/sends/messages and generated
subscription schema are enforced. Commands remain HTTP+CSRF. Explicit pinned
websockets17.4 and Uvicorn protocol/size/queue settings enable actual WS transport.
Protocol logs that include raw URI/query are suppressed; allowlisted close-code,
request-id/duration logs and bounded metrics retain application observability.

Friend UI adopts atomic controls before sequence checks, reconnects with zero
on gaps, drops detached socket callbacks, bounds failures and keeps slower REST
polling as fallback. Real two-phone E2E now requires actual WS frames and connected
state. Local production frontend + actual Uvicorn + disposable SQLite accepted
both Android and iPhone scenarios (2 PASS); PG races remain separate CI evidence.
The initial parallel development/SQLite harness hit a StrictMode command race;
production-build serial harness avoids claiming SQLite row-lock concurrency.

Full local backend551 PASS/22 SKIP before final delete/ready-reference additions;
web55 PASS before the final snapshot-hook case, final hook/transport4 PASS;
50 contract goldens/generation and structural compatibility PASS; build/lint and
UI-only demo3 PASS. New real PG gated snapshot/replay vs writer regression added.
Surface preflight still blocks on two matchmaking routes; no full release signoff.


Final A-I12 local targets: realtime durable21 PASS (including real ready-result
references, undo replay and deleted user); web56 PASS; production build/lint PASS.
The main event+host target previously22 PASS. Await exact-head PG/Compose CI.


## A-I12 public acceptance

PR43 merged e20f85923aabf7361658e63c940f14a03d246e59 after all six jobs PASS in
42537721404 on2ecd6788172db896c7dde6ed6f71cc470f10e977; exact merge42538048417
also PASS. The real PG gated snapshot/replay race passed. All four tested images
2ecd678 deployed with matching host overlay; all health checks PASS. Private
pre-realtime application pg_dump retained. Public trusted HTTPS13/13 PASS in34.7s
at6 workers, including actual WSS event exchange on Android and iPhone, held poll
reload, learning, coach and AI. No host/VPN network inspection or changes.

## A-I14 server clock scheduler (CI acceptance pending)

Base e20f85923aabf7361658e63c940f14a03d246e59. Expand-only0006 adds a partial
index over active deadlines and a persisted monotonic clock observation. Existing
clock JSON remains rollback-compatible; a legacy migration test checks white,
black, waiting and stopped clocks byte-for-byte. The deadline worker and HTTP/
engine commands share one atomic timeout transition and outbox write. The worker
claims due games with SKIP LOCKED and rechecks the current board/clock under lock;
a corrupt projection is isolated without inventing a result or starving other games.

Friend invitations offer untimed and four clock presets. Clocks pause before
acceptance, display server time with monotonic browser projection and use fresh
snapshots after reconnect. AI/coach timed games also refresh while idle. A delayed
same-version read cannot rewind the displayed clock. No new clock/event wire shape.
Clock worker uses the API image and explicit loopback-only host overlay.

Full local backend559 PASS/23 SKIP, clock migration/scheduler6 PASS, Compose host
and probes5 PASS, web57 PASS, build/lint/Ruff PASS. New real PG double scheduler/
late move race and actual idle timeout on both browser participants added to CI.
The public deployment still runs tested A-I12 until this stage passes acceptance.
Matchmaking and rated settlement next; existing draw command authority retained.
