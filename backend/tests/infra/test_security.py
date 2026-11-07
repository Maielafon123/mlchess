import pytest

from backend.app.infra.security import RateLimitExceeded, SlidingWindowLimiter, redact


def test_sliding_window_limiter_expires_old_events():
    limiter = SlidingWindowLimiter(2, 10)
    limiter.check("user", now=0)
    limiter.check("user", now=1)
    with pytest.raises(RateLimitExceeded):
        limiter.check("user", now=2)
    limiter.check("user", now=11)


def test_redaction_removes_credentials_and_bearer_tokens():
    safe = redact("password=secret authorization=Bearer abc123")
    assert "secret" not in safe and "abc123" not in safe
