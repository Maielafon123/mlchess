# ADR 0001 — Pure game history and draw adjudication

Status: local A-007 review candidate; CI and A+B contract review pending.
Date: 2026-11-07. Depends on A-001 game semantics and pinned chess 1.11.2.

The new `backend.app.games.domain` module is a pure immutable rules library.
It imports chess/PGN and the standard library, not HTTP, ORM, Redis, engine or
LLM components. It exposes internal domain values, not a second set of hand-
maintained API DTOs. A-008 maps these values into the A-003 generated models.
Historical `chess_ai/`, its draw policy and all legacy ML tests are unchanged.

A domain instance contains canonical initial FEN, contiguous UCI/SAN MoveRecords,
command version, terminal result/reason and an optional draw offer. Construction
replays the complete line, rejecting illegal moves, wrong SAN/ply, continuations
after terminal results and inconsistent adjudication metadata. Public board
access returns a copy with the full move stack. New commands return new domain
instances and do not mutate earlier states. The internal board cache is never
returned directly; repetition checks use a private copy as python-chess can
pop/replay history while testing a claim.

Normal public games start from standard chess.STARTING_FEN. The alternate
initial-FEN argument is only a trusted fixture/restore port for server code;
it is not accepted by CreateGameV1 and must not become a public arbitrary-FEN
endpoint. A FEN-only reconstruction cannot establish repeated positions.
Stored history, not a client's FEN, remains the authority for draw claims.

Each command requires the exact expected_version, and moves require the current
actor color. The actor must already have been resolved from an authenticated
participant by the service; passing a color is not user authentication. Immutable
version checks alone do not serialize concurrent writes. A-008 must perform
row locking, actor authorization, idempotency and state/event/outbox persistence
in one transaction before any event is published.

All UCI input is canonical standard chess. In particular rook-square castling
aliases such as e1h1 are rejected even though python-chess is_legal accepts them;
only e1g1 is recorded for that king-side castle. Null moves, SAN, whitespace,
uppercase and non-UCI suffixes are rejected. SAN is always produced by the board.
Castling, EP, captures and all four promotions are tested for both turn handling
and replay/export behavior. PGN exports the actual current line and result,
including SetUp/FEN for trusted nonstandard fixture starts.

Automatic outcomes use `Board.outcome(claim_draw=False)`: mate, stalemate,
insufficient material, fivefold repetition and 75-move automatic draws. Mate
takes precedence when the 150th quiet halfmove delivers checkmate. Threefold
and 50-move eligibility never finish a game without an explicit claim command.

The v1 claim-draw request contains no intended move. Therefore a claim is tested
on the **current** board with is_repetition(3) or is_fifty_moves(), by the player
to move. can_claim_threefold_repetition()/can_claim_fifty_moves() also consider
hypothetical next moves; accepting that broader predicate without recording the
intended move would accept a claim that the v1 command never identified. Adding
prospective claims requires a reviewed request/fixture extension. Tests cover the
7-ply repetition and 99-halfmove boundaries that expose this distinction.

A draw offer is PvP-only and can be accepted only by the other participant.
It survives a move by the offerer, is declined by an opponent move, and cannot
be silently replaced by another offer. Any terminal action clears it. Resign,
agreement and claim advance version without fabricating a move. A-009 adds solo
branch takeback; the pure library does not add any takeback or analysis endpoint.

`games.clocks.ClockPolicy` defines a pure deadline/transition port using trusted
server UTC and a new immutable clock state. A-019 implements persisted clock
accounting, increments and timeout races; this ticket makes no real-time or
clock-authority claim. A-005/A-006/A-008 remain the next persistence/auth/service
dependencies. No database migration or public schema change belongs to A-007.

Validation: deterministic unit fixtures for special moves, full-history claims,
3/5 repetitions, 50/75 moves, terminal precedence, turn/version, offer lifecycle,
immutable restoration and PGN round trips; seeded legal play compared with
python-chess. Run `python -m pytest backend/tests/games -q` plus the repository
contract/backend/legacy checks before a PR. Local commits remain review candidates.
