"""Performance analytics exposed through the public package."""

from space_pv_analytics import (
    add_power,
    add_robust_baseline,
    daily_health,
    detect_persistent_loss,
    estimate_degradation,
    summarize_case0,
)

__all__ = [
    "add_power",
    "add_robust_baseline",
    "daily_health",
    "detect_persistent_loss",
    "estimate_degradation",
    "summarize_case0",
]
