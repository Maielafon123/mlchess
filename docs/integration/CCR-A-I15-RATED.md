# A-I15: durable rated queue and exactly-once Elo

Base 97960c9502c77f61ab49162750781a6d8c1fc72f (clock PR44 in acceptance).
The user authorized completing the A/B integration without human review gates.
This records the B client change and A-owned expand-only migration.

Old: the B screen calls unmounted endpoints and models an invented rated-game
shape. In-memory queue/Elo modules are scaffolding; public rated create is denied.

New: account-only SQL tickets, two fixed time-control pools, 120-second TTL,
oldest compatible opponent within 400 Elo, no self-pair, one live ticket and one
active rated game per actor. Guests retain the existing invitation flow and
cannot enter the rated queue. Use generated ticket/pool/game-details DTOs.

HTTP: GET matchmaking/pools, GET matchmaking/current, POST matchmaking/tickets
with `{"schema_version":1,"pool":"rapid-10+0"}`, GET/DELETE an owned ticket.
POST/DELETE require Origin, session, CSRF and UUID command receipts; exact retries
return the original response. Matched tickets cannot be cancelled. A committed
pair creates two participants, one authoritative timed GameSnapshotV1, and the
initial event atomically. No public create endpoint accepts `mode=rated`.

Rated players read `/api/v1/games/{game_id}/rating`; all human game participants
read `/api/v1/games/{game_id}/actions` for available draw commands. Action and
rating reads are versioned projections, not changes to existing GameSnapshotV1.
Moves/resign/draw remain the existing HTTP+CSRF commands and game WSS stream.
No live PvP analysis, hints or takeback. Only the two participants can read results.

Elo starts at1200, K=32, independent per pool. Bounds100..4000 apply symmetrically
to the two-player delta. Terminal game result, both ratings, one settlement audit
row keyed by game ID, state/clock/event/outbox commit together. No rating from a
client-supplied result, repeated callback, or orphaned partial match. A global
PostgreSQL queue advisory lock protects admission/pairing; existing game row lock
protects settlement, with rating rows locked in sorted actor order.

Tests: guest/anonymous/foreign ACL, CSRF, cancellation-vs-match and simultaneous
join races, expired ticket, fixed pools, no self-pair, exact receipts, real moves,
draw/resign/timeout settlement, no double settlement after restart, and two real
account browsers against Compose. Production OIDC remains separately configured;
development login is never enabled on the public VPS to test this feature.
