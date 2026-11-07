# Durable gameplay worker

The API and gameplay worker run as separate processes. No Stockfish process is
started by an HTTP handler. Apply migrations through `0003_worker_jobs` before
starting either process; readiness checks include the new queue/move columns.

From the repository root, with `MLCHESS_DATABASE_URL` pointing to PostgreSQL:

```powershell
python -m alembic -c backend/alembic.ini upgrade head
$env:MLCHESS_STOCKFISH_BINARY = 'C:\path\to\stockfish.exe'
$env:MLCHESS_STOCKFISH_SHA256 = 'SHA256_FROM_THE_VERIFIED_BINARY'
python -m backend.app.workers.runner
```

`--once` processes at most one ready job, useful for a smoke check. Development
and tests may use `--fake`; staging/production rejects it. The real adapter
requires a pinned binary/hash in the CLI. Threads=1, Hash=32 MB, fixed profile
budgets and bounded UCI communication limit resource use. Profiles are skill
settings, not claims of a calibrated human Elo. The adapter sends the complete
move stack and validates every returned move/PV; evaluations have white POV and
mate is never represented as centipawns.

## Execution and recovery

The accepted command writes a `worker_jobs` row and its outbox source atomically.
`published_at` is a delivery acknowledgement, not execution completion. This
worker can poll PostgreSQL directly, so a Redis loss does not lose engine work.
RQ/broker transport and realtime fanout remain separate integration work; this
slice does not claim they are already deployed.

Workers claim using `FOR UPDATE SKIP LOCKED`, a lease deadline and random fencing
token. An expired lease can be reclaimed after a crash. Before applying a move,
the worker locks the game/job and rechecks mode, phase, turn, version, revision,
lease token/deadline and the legal move against full history. A delayed reply
after takeback is marked stale; duplicate delivery cannot create another ply.
The move/event/job completion commit together. Engine moves carry a unique job
identity rather than pretending to be an authenticated human.

Engine failures get bounded retries/backoff and then durable failure. A crash on
the final attempt is also finalized after lease expiry, rather than remaining
running forever. A failed engine does not remove the player's ability to resign
or take back. Operators can inspect job status/failure_code without raw provider
output or secrets being logged.

```powershell
python -m pytest backend/tests/engine -q
# The URL must be disposable; each test owns only generated schemas/databases.
python -m pytest backend/tests/games/test_postgres_commands.py backend/tests/games/test_postgres_worker.py -q
```

The process test closes the first API, launches an independent worker process,
then opens a fresh API and verifies the persisted reply. Migration/recovery CI
also covers the new job table and audited move foreign key. Keep old expanded
schemas on an application rollback; do not discard job/move audit evidence.
