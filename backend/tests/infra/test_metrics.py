import pytest

from backend.app.infra.metrics import MetricsRegistry


def test_metrics_registry_counts_and_sorts_labels():
    metrics = MetricsRegistry()
    metrics.increment("http_requests", method="POST", status="200")
    metrics.increment("http_requests", status="200", method="POST", value=2)
    assert metrics.snapshot() == {'http_requests{method="POST",status="200"}': 3}


def test_metrics_registry_bounds_series_and_rejects_invalid_input():
    metrics = MetricsRegistry(max_series=1)
    metrics.increment("first")
    metrics.increment("second")
    assert metrics.snapshot() == {"first": 1}
    with pytest.raises(ValueError):
        metrics.increment("")
