# A-002: analysis facts (review candidate)

Depends on the A-001 candidate schemas; not accepted v1 until A+B review and CI.
There are no engine processes, HTTP handlers or authorization implementations in
this contract PR. A-010/A-014 implement engine execution and result persistence;
A-013 supplies the shared access policy. Fixtures unblock B-001 and B-010 mocks.

`AnalysisRequestV1` identifies a move in the authenticated participant's game.
It accepts `ply` and `analysis_level: quick|deep`, plus a mandatory UUIDv4
`Idempotency-Key` HTTP header. All positions and resource limits come from the
server. An accepted job captures `game_id`, `revision`, `ply`, `position_key`;
the worker repeats participant/phase checks and compares the captured branch
before executing and before writing results. Active friend/rated requests,
result reads, cache reads and ready notifications require deny-by-default guards.
These policies cannot be established by JSON Schema alone.

`AnalysisJobV1` exposes durable `pending/running/done/failed` states. Pending or
running jobs contain null result/error, done requires `analysis_id`, failed
requires sanitized `ProblemDetailsV1`. Redis publication is not a done state.
Error and completion timestamps do not expose worker internals.

`AnalysisResultV1` reports engine facts and chess evidence, with no LLM text:

- `ScoreV1` is either `{kind: cp, value: int, pov: white}` or
  `{kind: mate, value: int, pov: white}`. Positive means White has the advantage
  or a forced mate; negative means Black. Mate zero is a terminal board, whose
  side-to-move identifies the mated side. Never convert mate distances to cp.
- Both `score_before` and the first candidate score evaluate best play at the
  before position. `score_after` evaluates the position after the played move.
  With two cp scores, loss is `max(0, (before - after) * mover_sign)` where the
  sign is +1 for White and -1 for Black. Any mate score forces `cp_loss: null`
  and `quality_method: mate-score-v1`, including a missed mate followed by a cp
  score. Quality labels are engine classifier output, not facts assigned by an
  LLM. A-014 must configure and test classification thresholds before runtime use.
- `top_moves` has 1–3 candidates ranked from the moving side's point of view.
  Each `uci` begins its `pv_uci`; SAN is computed at `before_fen`. Each PV is
  replayed for legality. Effective `engine.multipv` determines the number of
  candidates, capped by the number of legal moves. The verifier compares typed
  scores for ordering without translating mate into centipawns.
- `position_key = sha256(before_fen + "|" + played_move_uci)` binds the job to
  its chess input. An engine cache key must additionally include engine version,
  NNUE/model hash, budgets, MultiPV and schema version. Position keys confer no
  authorization and do not replace branch/revision checks.
- Effective engine metadata includes version, binary/NNUE SHA256, Threads,
  Hash, MultiPV and explicit nullable `time_ms/nodes/depth`; at least one limit
  is non-null. The v1 maxima are 30 seconds, 10M nodes, depth 64, MultiPV 3,
  Threads 4 and Hash 512MB. These output bounds do not grant clients the right
  to choose worker budgets: quick/deep are server allowlisted profiles.
- `facts.checks` and `facts.captures` describe the played move. `material_delta`
  is material gained by its mover using P=100, N=320, B=330, R=500, Q=900; this
  material count is separate from engine evaluation. Promotions and en passant
  use actual before/after material, not destination-square guesses.
- V1 verified motifs are checkmate, promotion, en passant and castling. Claim
  kinds are check, capture, promotion and checkmate, each with typed evidence
  and a unique UUID `fact_id`. No free-form threats, motifs or prose are accepted.
  B can refer to these IDs in its own `claim_refs`; adding claim kinds needs
  cross-owner contract review. Chess legality does not prove engine evaluations.

All sample evaluations and engine hashes are **synthetic fixtures** (`fixture-1`),
not Stockfish benchmarks or real analysis. Move legality, FEN, SAN, evidence,
material, score POV arithmetic and references are checked mechanically. Examples
cover White/Black, mate and missed mate, capture, EP, castling and promotion.
