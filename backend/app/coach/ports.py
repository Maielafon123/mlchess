"""A-owned integration ports for the B coach domain.

These protocols deliberately contain no FastAPI, SQLAlchemy or authentication
implementation. A's composition root supplies concrete adapters after the
analysis, session and queue contracts are ready.
"""

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from .grounding import AnalysisFacts
from .providers.base import CoachRequest
from .service import CoachJob


@runtime_checkable
class PrincipalAccessGuard(Protocol):
    """Authorize one actor for one game/coach request."""

    def __call__(self, request: CoachRequest) -> bool: ...


@runtime_checkable
class VerifiedAnalysisReader(Protocol):
    """Read only a server-verified analysis for the requested game revision."""

    def __call__(self, request: CoachRequest) -> AnalysisFacts | None: ...


@runtime_checkable
class CoachJobsPort(Protocol):
    """Durable idempotent job store; implementation belongs to A."""

    def find_by_key(self, cache_key: str) -> CoachJob | None: ...

    def create(self, request: CoachRequest, cache_key: str) -> CoachJob: ...

    def get(self, job_id: str) -> CoachJob | None: ...

    def save(self, job: CoachJob) -> None: ...


@runtime_checkable
class QueueEnqueue(Protocol):
    """Bounded worker enqueue operation with no provider credentials in B."""

    def __call__(self, job_id: str) -> Awaitable[None] | None: ...


CoachJobKey = Callable[[CoachRequest], str]
