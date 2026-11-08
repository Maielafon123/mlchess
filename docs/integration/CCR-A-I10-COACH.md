# A-I10 guarded durable coach composition

This records the cross-owner changes before implementation. The user explicitly
authorized completion of the whole project without waiting for human review.
Andrei's B-05 ports were read and merged before this work.

A supplies asynchronous SQL orchestration around B's pure CoachService and
grounding validator. SQL receipts/jobs/explanations are authoritative; the B
service instance is a single worker execution, never an HTTP job store. The
existing synchronous ports are suitable for a loaded snapshot inside that worker,
not blocking SQL calls on the API event loop. No process-global actor guard.

B's router gains a guarded durable factory. Only game-scoped routes are mounted;
GET repeats session, participant, phase, analysis identity and revision checks.
The old unscoped in-memory factory remains a test helper and is not mounted.
Provider work runs after the analysis is ready, in a separate bounded worker.

No remote model credentials are configured. A truthful rule-based provider can
explain verified engine facts without external calls or fees; it is identified as
verified-rules-v1, not an LLM. Malformed/unavailable providers use B's deterministic
fallback. Provider substitution requires allowlisting, bounded transport and the
same grounding gate. No fake provider is used in production.

Preserve coach request/job/explanation JSON contracts. Add one expand-only
coach_explanations migration with foreign keys and request uniqueness. Add
contract, restart, foreign-job, active-PvP, stale-undo and provider-failure tests.
The UI obtains context only from a real AnalysisResult, clears old hints on
identity/revision changes and resumes the same game after refresh.

The request cache also includes the principal. This is a deliberate tightening of
B's proposed key: future student context must not leak to the other participant.
Both job GET and cached submit require the original principal as well as the game
ACL. A second participant receives their own otherwise-equivalent job.
