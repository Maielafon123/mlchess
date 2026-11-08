# A-I11 persistent learning integration

User authorized completion of the whole project. This CCR records A's concrete
SQL, migration, router and consumer work across B's handoff before editing it.
B's puzzle grading and progress rules remain the pure execution boundary.

One expand-only migration adds curated lessons/puzzles, principal-scoped lesson
status, puzzle cursor/hint state, attempts, skill rows, progress events and learning
receipts. The grader receives only persisted puzzle/solution state. Attempts and
progress commit in one actor-locked transaction; both header command keys and
(student_id, attempt_id) deduplicate exact payloads and reject changed replay.

Existing LessonV1/PuzzleV1/PuzzleAttemptV1/StudentProgressV1 wires are retained and
projected into generated OpenAPI/TS/runtime models. Add explicit list/detail/status,
hint, puzzle-state, progress/review and own-data export/reset contracts. PuzzleV1
contains no solution. Puzzle state reveals the legal solution only after completion;
progressive hints reveal only one requested hint. Server counters record hints.

GET progress binds the session principal. Foreign student IDs are denied, never
used as an unguarded storage key. Expiring guests use the same persistent ports.
The reset endpoint deletes learning data only and is tested on disposable data;
no live user's data is removed as part of development.

Curated content is original MLChess curriculum with explicit provenance/license
and legal-line validation. Repository source URLs replace nonexistent demo URLs.
Production UI uses real APIs and server lesson/puzzle/progress state; demo adapters
remain explicitly limited to the development/test demo mode. No pre-attempt
solution, is_correct input or browser-local progress can award server learning.

B grader integration accepts an alternative final move only when both the stored
line and the actual legal move independently end in checkmate for a mate puzzle.
This prevents rejecting a valid rook underpromotion in the original promotion
exercise. Persist actual played history and replay that verified completion.
Public provenance links to the curriculum document, which omits solution lines.

Learning commands echo a server learning_epoch, puzzle cursor and session number.
An own-progress reset retains only the technical epoch counter and increments it;
old tabs/queued requests cannot recreate erased progress. Account deletion can
remove that counter via its user foreign key. Export is cursor-paginated and all
solution-bearing state is emitted only after that principal completed the puzzle.
