from space_pv_analytics import (
    add_power,
    add_robust_baseline,
    daily_health,
    detect_persistent_loss,
    estimate_degradation,
)
from space_pv_connectors import make_demo_telemetry


def test_demo_pipeline_detects_persistent_loss() -> None:
    frame = add_robust_baseline(add_power(make_demo_telemetry(seed=42)))
    assert len(frame) > 1000
    assert frame["power_w"].min() >= 0
    health = daily_health(frame)
    start, loss = detect_persistent_loss(health)
    assert start is not None
    assert loss is not None and loss > 0.15
    estimate = estimate_degradation(frame)
    assert -10.0 < estimate.slope_percent_per_year < 0.0
