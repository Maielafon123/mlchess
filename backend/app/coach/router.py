"""Coach router boundary.

The A-owned application composition will mount this router in an integration PR.
No endpoints are registered until the A-owned AnalysisReader and auth/mode guards
are available, so this module deliberately contains only the router object.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["coach"])
