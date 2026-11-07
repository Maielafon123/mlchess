# A-001/A-002: common, game and analysis contracts (review candidates)

These are JSON Schema 2020-12 YAML sources, not implemented HTTP endpoints.
A owns `common/`, `game/`, this validator and the matching fixtures. The first
contract gate remains pending B review and green CI. Once accepted, v1 changes
must follow compatibility review. Analysis/WS are specified in A-002; OpenAPI assembly,
generated Pydantic/TypeScript and compatibility/drift checks are supplied by A-003.
Generated API/model/type artifacts are never edited by hand. See [tooling/README.md](tooling/README.md) for the complete pipeline and its limits.

From a clean checkout, with Python 3.12+:

```bash
python -m venv .venv-contracts
. .venv-contracts/bin/activate
python -m pip install -r contracts/requirements.txt
npm --prefix contracts ci --ignore-scripts --no-audit --no-fund
python contracts/validate.py
python -m pytest backend/tests -q
python -m contracts.tooling.generate --check
npm --prefix contracts run typecheck
npm --prefix contracts test
ruff check backend contracts
ruff format --check backend contracts
```

Use a virtual environment outside the checkout if local ignore rules do not
exclude `.venv-contracts`. On Windows activate with
`.venv-contracts\Scripts\Activate.ps1`. The schemas use stable identifiers under
`https://mlchess.local/contracts/`; these are identifiers, not network endpoints.
The validator resolves every reference offline from this checkout, checks schema
syntax, rejects duplicate YAML keys and validates all 34 golden examples. It also
replays example histories with python-chess to verify FEN, SAN, ply and turn.
The fixture manifest maps each JSON payload to its schema; payload files contain
only the actual request or response, so frontend mocks can consume them directly.

Analysis details: [analysis/README.md](analysis/README.md). WebSocket cursor and
resync rules: [game/events.md](game/events.md). These extend the A-001 fixtures
for B-001/B-010 mocks while the same contract review gate remains pending.

## Wire decisions for B review

- Schema references are `common/v1.yaml#/$defs/ProblemDetailsV1` etc. All
  response objects carry `schema_version: 1`; commands follow the architecture's
  unversioned request bodies. Unknown object fields are rejected.
- IDs are lowercase UUIDv4; timestamps use real UTC dates with `Z`; counters
  and milliseconds are nonnegative integers within JavaScript's safe range.
- `CurrentUserV1.id` identifies the authenticated actor: account ID or opaque
  guest actor ID. `kind` distinguishes them; `display_name` is required and
  nullable. `expires_at` is the session expiration for either kind. Guest actors
  cannot use friend/rated; that requires runtime session authorization.
- The public create command accepts `friend`, `ai`, `coach`. `GameModeV1`
  additionally includes `rated`, whose games are created by matchmaking.
  `time_control` is required, nullable for unclocked games; solo creation also
  requires `human_color` and `ai_profile`, both forbidden in friend creation.
  Profiles are `beginner/casual/club/strong`, without a human rating promise.
- `Idempotency-Key` (UUIDv4 HTTP header) is mandatory for game creation. Moves
  use the mandatory body key `client_move_id`. Key scope is game + actor; equal
  payload retries return the exact persisted `MoveAcceptedV1`, even if the game
  later advances. Changed payload with the same key gives 409
  `IDEMPOTENCY_CONFLICT`. `expected_version` protects every mutation. A stale
  command gives 409 `STALE_GAME_VERSION`; reload the game with GET before retry.
- `MoveAcceptedV1` contains the acknowledged `client_move_id`, `move`, and full
  authoritative `snapshot`. The accepted snapshot increments version exactly
  once. `moves` is the entire current branch from the standard initial position;
  it replays to `fen`, `ply`, `side_to_move`. FEN uses python-chess's canonical
  `Board.fen()` (en-passant square only when a legal capture exists).
- Player slots have `side`, `kind: human|engine`, and required nullable `user_id`.
  A human has an actor UUID, an engine has null. Solo snapshots include both
  slots; a waiting friend game has just the creator. Active games have two
  distinct sides. A private snapshot is available only to participants.
- `time_control` and `clock` are both null for unclocked play. A clock contains
  remaining milliseconds, nullable `running_side`, and UTC `server_now` anchor.
  Waiting/terminal clocks are stopped; rated games always have a time control.
  Clocks are server values; clients interpolate only for display.
- `result` and `termination` are always present. Waiting/active: both null.
  Finished: both non-null; result is `white|black|draw`. Aborted: null result,
  `termination: aborted`. Threefold/50-move are explicit claims; fivefold/75-move
  are automatic adjudications. Runtime rules must replay the full move history.
- `capabilities` is viewer-specific and computed by the server. Active/waiting
  friend/rated have `can_analyze_now: false`; all friend/rated snapshots have
  `can_takeback: false`. Finished participants may obtain analysis. Capabilities
  never replace per-command session/actor/phase checks.
- Takeback requires explicit `plies: 1|2` and `client_action_id`. The UI sends
  two for a completed human/engine cycle, one while the engine is pending.
  `revision` increments and pending work must recheck the new revision. Prior
  branches are retained by the server, outside the current branch response.
- `ProblemDetailsV1` has typed codes paired with HTTP statuses, a UUID request
  ID and no traceback/debug fields. Examples cover 409 stale version and 422
  illegal move. Syntax validation does not establish move legality: the game
  domain must check legal moves, actor, turn, idempotency, version and clocks.

## Review and scope

This PR supplies typed mocks for B-004…B-009. Review the required/nullable fields,
player representation, explicit takeback extent and idempotent response shape
before accepting v1. It adds no runtime handlers, database migrations or changes
to B-owned code or legacy MLChess. Full backend tests and lint are applicable;
Alembic upgrade is not applicable until A-005 creates migrations. The small
contracts CI job checks this first deliverable; it is not the full A-024 pipeline.
