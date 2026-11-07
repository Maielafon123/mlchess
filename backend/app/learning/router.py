"""B-owned learning router boundary.

The application composition mounts this router only after A supplies session and
persistence dependencies. The exported router intentionally has no routes.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/learning", tags=["learning"])
