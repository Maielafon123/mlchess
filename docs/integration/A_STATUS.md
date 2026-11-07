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

Next smallest task: A-I00/A-I01 same-origin Compose and B wire acceptance.
