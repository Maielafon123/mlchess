# A-002: game WebSocket stream (review candidate)

`events.v1.yaml#/$defs/GameEventV1` is a discriminated union of the eight
architecture-defined event types. It describes server messages, not write
commands. HTTP remains the only game-command surface. Matchmaking uses ticket
REST polling until a game exists; `matchmaking.matched` is not a game event.

Every frame contains `schema_version`, UUID `event_id`/`game_id`, integer `seq`,
`type`, UTC `occurred_at`, and a payload specific to that type. Unknown fields,
types and mismatched payloads fail validation. Sequence numbers and game
versions are independent: analysis completion or clock events can advance seq
without accepting another game command.

## Durable events

These six events have `seq >= 1`. Allocate their sequence in the same Postgres
transaction as state/event/outbox. Publish only after commit; Redis is transport.
Delivery can repeat. Clients apply `last_seq + 1`, ignore already applied seq,
and request resync on a gap. Never apply an event from another game or an old
revision to the current branch. Reauthorize live subscriptions and result reads.

| Type | Payload |
| --- | --- |
| `game.move_committed` | version, revision, move (ply/UCI/SAN), FEN, next side, nullable clock |
| `game.status_changed` | version, revision, status, nullable result/termination/clock |
| `game.clock_sync` | version, revision, ply, non-null authoritative clock |
| `game.takeback_applied` | version, from/to ply, new_revision, FEN, next side, nullable clock |
| `analysis.ready` | analysis_id, revision, ply |
| `coach.ready` | explanation_id, analysis_id, revision, ply |

Ready events carry only opaque result references. Fetching a result must check
participant, mode/phase, revision and position key again. Even a reference must
not be sent to participants in active friend/rated games. Coach explanation
content remains B-owned; no B schemas or pedagogical text are copied here.

## Bootstrap and recovery controls

`game.snapshot` and `server.resync_required` are connection control frames. Their
`seq >= 0` carries the current committed cursor and does not allocate a new event
or advance durable dedup by itself. Handle these two types before durable-event
sequence checks. Their event IDs identify the control delivery, not stored game
mutations. This distinction avoids creating new game events for every reconnect
and avoids persisting viewer-specific capabilities in a shared event log.

- A fresh connection (`after_seq=0`) receives an atomic `game.snapshot` containing
  a viewer-specific `GameSnapshotV1` paired with the game event head in envelope
  `seq`. After adopting that pair, accept only durable events with larger seq.
  Snapshot and cursor must come from the same transactionally consistent read.
  Handshake Origin, session and participant authorization are mandatory.
- For a valid retained cursor, replay all later durable events in order and then
  continue the live stream. Subscribe/buffer before reading the replay boundary
  to avoid losing a commit between replay and live fanout; bound the buffer.
- A cursor beyond the head, missing replay history, or detected gap produces
  `server.resync_required`. Its `seq` equals `payload.latest_seq`, with
  `after_seq` and a reason of `cursor_ahead`, `replay_unavailable`, or
  `sequence_gap`. The signal is not a successful replay acknowledgement.
- On resync, fetch the authorized REST snapshot, clear pending event deltas and
  reconnect with `after_seq=0` to obtain a fresh atomic snapshot/cursor pair.
  REST GameSnapshotV1 itself has no event cursor in the A-001 baseline; do not
  attach an old control cursor to a separately fetched newer snapshot.
- A takeback removes 1 or 2 current-line plies, advances version and revision,
  and invalidates pending engine/coach work. Prior lines remain auditable on the
  server. Queued events/results for previous revisions cannot change the branch.

The eight golden event files form a sample stream: bootstrap at seq 0; a move,
analysis-ready, coach-ready, clock sync, takeback, abort at seq 1–6; resync at
head 6 for client cursor 20. Tests replay the sequence and verify that a stale
control cursor cannot masquerade as a new game mutation. Runtime replay, fanout,
Origin/session/ACL and reconnection behavior arrive in A-017; this PR does not
claim those security or concurrency implementations exist.
