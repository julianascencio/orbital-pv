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
from space_pv_analytics.monitoring import (
    LogPowerTrend,
    MonitoringDesign,
    design_degradation_monitoring,
    fit_log_power_trend,
    log_power_covariance,
)

__all__ = [
    "LOSS_CATEGORIES",
    "LogPowerTrend",
    "LossStage",
    "MonitoringDesign",
    "PowerLossBreakdown",
    "PowerLossSummary",
    "add_power",
    "add_robust_baseline",
    "daily_health",
    "design_degradation_monitoring",
    "detect_persistent_loss",
    "estimate_degradation",
    "fit_log_power_trend",
    "log_power_covariance",
    "power_loss_breakdown",
    "summarize_case0",
    "summarize_power_losses",
]
