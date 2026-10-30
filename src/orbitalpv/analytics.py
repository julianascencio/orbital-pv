"""Performance analytics exposed through the public package."""

from space_pv_analytics import (
    LOSS_CATEGORIES,
    LossStage,
    PowerLossBreakdown,
    PowerLossSummary,
    add_power,
    add_robust_baseline,
    daily_health,
    detect_persistent_loss,
    estimate_degradation,
    power_loss_breakdown,
    summarize_case0,
    summarize_power_losses,
)

__all__ = [
    "LOSS_CATEGORIES",
    "LossStage",
    "PowerLossBreakdown",
    "PowerLossSummary",
    "add_power",
    "add_robust_baseline",
    "daily_health",
    "detect_persistent_loss",
    "estimate_degradation",
    "power_loss_breakdown",
    "summarize_case0",
    "summarize_power_losses",
]
