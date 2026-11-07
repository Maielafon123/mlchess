"""Public error mapping. Never copy exception text or request input into responses."""

from __future__ import annotations

from dataclasses import dataclass

from starlette.responses import JSONResponse

from backend.app.infra.generated.contracts import ProblemDetailsV1

# Public texts are fixed server messages; UI localizes machine-readable codes.
PROBLEMS = {
    400: ("BAD_REQUEST", "Bad request", "The request could not be processed."),
    401: ("UNAUTHENTICATED", "Authentication required", "A valid session is required."),
    403: ("FORBIDDEN", "Forbidden", "This request is not permitted."),
    404: ("NOT_FOUND", "Not found", "The requested resource was not found."),
    405: (
        "METHOD_NOT_ALLOWED",
        "Method not allowed",
        "This HTTP method is not available for this resource.",
    ),
    409: (
        "STALE_GAME_VERSION",
        "Game version conflict",
        "Reload the game snapshot before submitting a new command.",
    ),
    422: (
        "VALIDATION_ERROR",
        "Invalid request",
        "The request body or parameters are invalid.",
    ),
    429: ("RATE_LIMITED", "Too many requests", "Retry this request later."),
    500: ("INTERNAL_ERROR", "Internal error", "The request could not be completed."),
    503: (
        "SERVICE_UNAVAILABLE",
        "Service unavailable",
        "The service is temporarily unavailable.",
    ),
}


@dataclass
class PublicProblem(Exception):
    status: int

    def __post_init__(self):
        if self.status not in PROBLEMS:
            raise ValueError("Unsupported public error status")


def problem_response(status: int, request_id: str) -> JSONResponse:
    if status not in PROBLEMS:
        status = 500
    code, title, detail = PROBLEMS[status]
    payload = ProblemDetailsV1.model_validate(
        {
            "schema_version": 1,
            "type": "urn:mlchess:problem:" + code.lower().replace("_", "-"),
            "title": title,
            "status": status,
            "code": code,
            "detail": detail,
            "request_id": request_id,
        }
    )
    return JSONResponse(
        payload.model_dump(mode="json"),
        status_code=status,
        media_type="application/problem+json",
    )
