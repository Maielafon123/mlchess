# A-027 integration evidence

Status: **release blocked**. This integration combines the A foundation with B's
`codex/review-hardening` at `9a985d9`. Passing library and UI demo tests is not
evidence that a deployed game can be played end to end.

## Verified locally on Windows / Python 3.12 / Node 24

- Combined backend: 432 passed, 2 skipped. Two additional release-preflight
  regression tests passed separately after their addition.
- Frontend: 42 tests passed; ESLint and TypeScript/Vite production build passed.
- Playwright: 3 navigation/demo smoke tests passed. They do not exercise live
  backend gameplay. Legacy ML regression: 19 passed with CPU PyTorch 2.10.0.
- Built and installed the backend wheel in a separate environment; isolated
  Python imported coach providers and the packaged coach schema from
  site-packages and constructed the application successfully.
- PostgreSQL 16: Alembic upgrade SQL applied to a new disposable database;
  `pg_dump -Fc` restored into a second empty database. Result, final FEN, all
  four moves, two users and a pending outbox row matched. Temporary databases
  were removed. Example observed backup/restore: 0.453 / 0.609 seconds, 20,662
  archive bytes. These synthetic timings are not production RPO/RTO.
- `python -m infra.release_check` correctly exits 1: 18 required HTTP operations
  and the game WebSocket are absent from the composed application.

## Blocking dependencies

| Dependency | Actual gap | Required acceptance evidence |
| --- | --- | --- |
| A-006 | In-memory dev sessions; no OIDC/guest or durable session adapter | Production auth, expiry/revoke and session ACL tests |
| A-008/A-009 | In-memory command boundary, no game HTTP handlers | Real PostgreSQL commands, idempotent responses, race tests, solo takeback |
| A-011/A-012/A-014 | Outbox/worker/analysis primitives; no running job pipeline | Durable jobs, legal AI replies, stale-result guards, engine-derived results |
| A-015/A-016 | Empty mounted B routers; B factory/proposals imported only | Authenticated game-scoped coach/learning composition and migrations |
| A-017–A-021 | Library-only events/invites/clocks/matching/ratings | HTTP/WS two-browser games, reconnect, timeouts, one-time rating settlement |
| A-022–A-025 | Partial middleware/metrics/CI; infrastructure-only Compose | Production service wiring, security/load gates, staging deployment |
| A-026 | Local synthetic restore now reproducible | Encrypted offsite/PITR, worker redispatch, deployed migration/rollback rehearsal |
| A-027 | No four-mode and learning staging acceptance | Two-browser E2E, dependency/license inventory and deployment evidence |

The earlier commit subjects A-024/A-025/A-026 describe smaller primitives and do
not establish completion of the corresponding roadmap tasks. A-027 must remain
open until the dependencies above are implemented and the real acceptance flows
pass. No production deployment or release tag is created by this integration.

## Reproducible checks

Run from the repository root after installing backend/contract dependencies:

```powershell
python -m pytest backend/tests -q
ruff check backend contracts infra
ruff format --check backend contracts infra
python -m contracts.tooling.generate --check
pnpm --dir apps/web install --frozen-lockfile
pnpm --dir apps/web run lint
pnpm --dir apps/web run build
pnpm --dir apps/web run test
pnpm --dir apps/web run test:e2e
python -m infra.release_check
python -m infra.recovery_drill --container mlchess-postgres --user mlchess
```

The final preflight is expected to fail until the composed routes exist. It
normalizes route parameter names, checks HTTP methods and distinguishes real
WebSocket routes from HTTP routes. Passing it later only establishes that the
surface is present; it does not replace the acceptance evidence above.
