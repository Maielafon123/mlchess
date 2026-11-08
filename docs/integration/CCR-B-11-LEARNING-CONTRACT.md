# CCR-B-11 — Learning API and persistence handoff

The existing versioned schemas cover lesson, puzzle, puzzle-attempt and student
progress response objects. B will keep `solution_uci` out of pre-attempt puzzle
responses and will grade attempts server-side with an idempotent `attempt_id`.

## Required API surface

- lesson list/detail and completion/status mutation;
- puzzle fetch, progressive hint and server-graded attempt;
- progress/review queue, export and account deletion;
- ownership/session rules for account and expiring guest identities.

## Required A store ports

A must provide SQL-backed ports for lessons, puzzles, attempts, student skills,
progress events and atomic attempt+progress commit. The deduplication key is
`(student_id, attempt_id)`; replay returns the original result without awarding
progress twice. Cross-user reads and writes must be denied.

## Acceptance boundary

This CCR freezes the B domain expectations but does not claim that the current
empty learning router is production-ready. B can test the pure grader and fake
store; live routes stay **BLOCKED on A** until an `A-CONTRACT-READY` SHA includes
migrations, concrete ports, ACL negatives and an HTTP example.
