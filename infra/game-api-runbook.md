# Durable game HTTP slice

The application now registers create/get/move/takeback, resign, draw-offer,
accept-draw and claim-draw handlers. Auth sessions and command responses use the
same database when `MLCHESS_DATABASE_URL` is set. With no database configured,
game handlers return a sanitized 503. Deployed readiness also returns 503 until
persistence is configured and the `game_states` table is queryable.

## Local startup (PowerShell, repository root)

```powershell
docker compose -f infra/compose.dev.yml up -d
$env:MLCHESS_DATABASE_URL = 'postgresql+asyncpg://mlchess:mlchess_dev@127.0.0.1:55432/mlchess'
$env:MLCHESS_PUBLIC_ORIGIN = 'http://127.0.0.1:8000'
$env:MLCHESS_DEV_AUTH_ENABLED = 'true'
python -m alembic -c backend/alembic.ini upgrade head
python -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log --no-server-header
```

Dev login accepts `display_name`: two different fixture names create distinct,
deterministic development accounts so local two-user checks are possible. This
is not production authentication; the configuration guard forbids dev login in
staging/production. Session tokens remain random, opaque, hashed and revocable.

After dev login, send its cookies, `Origin` and `X-CSRF-Token` (from the CSRF
cookie) on writes. Create uses a UUIDv4 `Idempotency-Key` and this body:

```json
{"mode":"coach","time_control":null,"human_color":"white","ai_profile":"casual"}
```

Move body: `client_move_id` UUIDv4, integer `expected_version`, canonical `uci`.
The response is `MoveAcceptedV1` with a nested `snapshot`, not a bare snapshot.
Takeback body: `expected_version`, explicit `plies` (1 or 2), `client_action_id`
UUIDv4. Other actions use `GameActionV1` (`expected_version`) and a UUIDv4
`Idempotency-Key` header. Client FEN, result, clock values or engine budgets are
not accepted as authoritative state.

## Guarantees and verification

PostgreSQL locks serialize the actor and game in a consistent order. A command
commits full replayable history, immutable move rows, game events, outbox rows
and its exact response in one transaction. A repeated key with the same command
returns the original response even after later moves/takebacks or an API restart;
a changed payload returns 409. No event is sent directly before commit.

Clock accounting uses PostgreSQL `clock_timestamp()` after lock acquisition.
A late move commits the timeout result but rejects the move; elapsed time never
comes from the client. Threefold claims replay the complete stored move line.
Takeback retains old lines, advances revision and is forbidden in PvP.

```powershell
python -m pytest backend/tests/games/test_http_games.py -q
# Use only a disposable PostgreSQL server. Tests create/drop their own random schemas.
$env:MLCHESS_TEST_DATABASE_URL = 'postgresql+asyncpg://mlchess:TEST_PASSWORD@127.0.0.1:TEST_PORT/TEST_DATABASE'
python -m pytest backend/tests/games/test_postgres_commands.py -q
python -m infra.recovery_drill --container mlchess-postgres --user mlchess
```

SQLite is a sequential local/test convenience, not proof of concurrent command
correctness. CI runs the concurrency suite against PostgreSQL 16.

## Migration and integration boundaries

Migration `0002_game_commands` only adds tables/indexes. Roll back application
code with the expanded schema retained; its downgrade deliberately refuses to
discard response/history evidence. Pre-existing synthetic baseline game rows
without full `game_states` history return 503 until explicitly imported with
trusted complete history; a bare FEN is not silently promoted to a valid game.

AI turns are now durably requested in outbox, but the running engine worker is
the next dependency. Friend creation waits for the A-018 invitation acceptance
flow. Production OIDC/guest auth, WebSocket fanout, analysis, coach and learning
composition remain separate dependencies. The current B temporary clients need
to adopt the generated request/response types described above; do not weaken the
server contract to accept their old partial payloads.
