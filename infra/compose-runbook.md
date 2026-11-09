# Private same-origin application stack

This is a development integration stack with real SQL sessions, API commands
and a real pinned Stockfish worker. It is NOT production signoff. Google OIDC,
domain/TLS, remaining product endpoints and offsite recovery still block release.
Redis is isolated and ready for transport; current gameplay leases are polled
directly from PostgreSQL. Do not claim Redis redispatch is verified.

From the repository root, with Docker Desktop using Linux amd64 containers:

```sh
python -m infra.init_compose_env --origin http://localhost:8080
docker compose --env-file .env.dev.local -f infra/compose.app.yml config --quiet
docker compose --env-file .env.dev.local -f infra/compose.app.yml up -d --build --wait
```

Open http://localhost:8080. Default guest mode establishes a real SQL session
automatically. MLCHESS_WEB_AUTH_MODE=development selects manual dev login;
production forbids development/fake auth. Named volumes retain games and jobs.
The API and worker run separately with non-root UID, bounded CPU/RAM, read-only
root filesystems and no capabilities. Learning runs separately with a restricted
PostgreSQL role. If upgrading an older local env file, add a unique random
URL-safe `MLCHESS_LEARNING_PASSWORD` and `MLCHESS_RELAY_PASSWORD`
(each at least 43 characters) before startup.
PostgreSQL/Redis have no published ports.
Only the gateway publishes a loopback port. Network subnets can be overridden
with MLCHESS_EDGE_SUBNET and MLCHESS_DATA_SUBNET after checking host routes.

On Linux the initializer creates the secret env file exclusively with mode0600;
on Windows inherit only the intended account's directory ACL. Never commit or
copy its contents into tickets, logs or Docker build context. Do not run plain
`docker compose config` in shared logs: it expands passwords. Use `config --quiet`.

Run live acceptance separately from frontend-only demo tests:

```powershell
$env:MLCHESS_LIVE_BASE_URL='http://localhost:8080'
pnpm --dir apps/web test:e2e:live
pnpm --dir apps/web test:e2e
```

The live suite uses Chromium/WebKit contexts, real durable sessions, ACL,
human move, background engine reply, persisted snapshot and takeback. It does
not mock API requests. Failure traces may contain test session cookies: keep
test-results private; Docker/Git exclude them. No real OAuth secrets are used.

Add -f infra/compose.static-test.yml after the base Compose file to test the
actual static build. CI uses this overlay. Public deployment uses the separate
compose.server.yml and [server runbook](server-runbook.md), with dev auth disabled.

Stop containers while retaining data:

```sh
docker compose --env-file .env.dev.local -f infra/compose.app.yml down
```

Never add `--volumes` against an installation containing valuable data. Schema
migrations are expand-only; rollback uses a compatible previous application
image and retains expanded schema/audit. Back up PostgreSQL before upgrades.

For a VPS, deploy this private preview only on loopback and access via an SSH
local forward. Do not expose development auth to the internet. Existing VPN,
firewall, routes, sysctls and host Docker service must remain untouched. Public
production deployment requires a separate reviewed TLS/OIDC configuration.
The 2CPU/4GiB host budget is respected by container limits; do not build models
or copy training datasets into this stack. Linux Stockfish15.1-4 is GPLv3;
package copyright/source references remain under /usr/share/doc/stockfish.
