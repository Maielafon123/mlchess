# A-004: backend scaffold (local review candidate)

Depends on A-001 common contracts, with A-003 generated models. All work is local;
contract acceptance, CI and review remain pending. The only implemented routes
are `GET /health/live` and `GET /health/ready`. Game/session/engine APIs remain
proposed; no database, Redis, migration or engine process is started here.

From repository root, Python 3.12+, using an activated virtual environment:

```bash
python -m pip install -c backend/requirements.lock -e './backend[dev]'
python -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log --no-server-header
```

`infra/backend.env.example` lists the supported environment variables, without
secrets. Settings are read from `MLCHESS_*`; dotenv files are not implicitly
loaded. Normalized PUBLIC_ORIGIN supplies the one allowed HTTP origin and Host.
Use a same-origin frontend/proxy. In staging/production HTTPS is mandatory and
development authentication cannot be enabled. Swagger, ReDoc and the runtime
OpenAPI URL are disabled in all environments. This ticket adds no dev login.

Liveness returns `HealthV1` while the process can answer HTTP. Readiness returns
200 only during the lifespan and after each registered dependency check returns
None. Failure, an invalid probe result or timeout returns a generic 503 problem,
without database/host/credential details. Before A-005/A-011 register DB/queue
checks, readiness establishes only scaffold lifecycle health; it is not a claim
that gameplay is available. Probe count and total elapsed budget are bounded.

All HTTP errors use `ProblemDetailsV1` with a server-issued UUIDv4 request ID,
which is also returned in `X-Request-ID`. Untrusted request-ID headers are never
reflected. Validation errors omit input values; unhandled exceptions omit their
message and traceback. A ContextVar is isolated per request and restored after
completion. Responses have no-store/nosniff and no cross-origin credential grants.

GET/HEAD may omit Origin for probes and CLI clients; any Origin supplied must
match the public origin. Mutations must supply the same-origin header. This is
an early Origin/Host guard, not completed CSRF/session/rate-limit middleware:
A-006 and A-022 add those checks before any authenticated mutation is exposed.
Logs contain only event, request_id, method, actual HTTP status and elapsed
milliseconds. Do not enable Uvicorn access logs: they can include query strings.
Health responses do not leak readiness dependency names or failure reasons.
A failed stream already started cannot change status; it is closed without
publishing exception details. Current scaffold routes do not stream bodies.

Schema changes: add HealthV1 and its operational routes, plus an explicit
METHOD_NOT_ALLOWED/405 pair missing from the initial common draft. Regenerate
all artifacts using A-003. This enum correction requires review and incorporation
into the first accepted v1 baseline; the conservative compatibility gate correctly
flags it against the earlier A-003 proposal. No compatibility bypass is added.
If v1 is accepted before this correction, it needs the agreed version migration
process rather than silently changing a published enum.

Checks from root (install contract tools and `npm --prefix contracts ci` too):

```bash
python contracts/validate.py
make contract-check
python -m pytest tests -q
python -m pip check
```

Backend packaging deliberately contains only A-owned backend modules. The
installed health service runs outside the source directory without contract
build tools, PyTorch, a GPU, external secrets or untracked files. Public schema
fixture validation remains a repository/tooling check. No migration is applicable
until A-005. Next dependencies: DB baseline A-005, then OIDC/session A-006; pure
chess rules A-007 can be developed independently of DB/HTTP.
