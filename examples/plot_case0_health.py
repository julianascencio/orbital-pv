"""
Telemetry-only daily health baseline
====================================

The Case 0 workflow provides a deterministic demonstration of upper-envelope
normalization and persistent-loss detection before full orbit normalization.
"""

import matplotlib.pyplot as plt

from space_pv_analytics import add_power, add_robust_baseline, daily_health
from space_pv_connectors import make_demo_telemetry

telemetry = make_demo_telemetry(seed=42)
normalized = add_robust_baseline(add_power(telemetry))
health = daily_health(normalized)
anomalies = health[health["is_anomaly"]]

fig, ax = plt.subplots()
ax.plot(health["day"], health["power_envelope"], label="Daily 95th-percentile envelope")
ax.axhline(1.0, color="black", linestyle="--", linewidth=1, label="BOL reference")
ax.scatter(
    anomalies["day"],
    anomalies["power_envelope"],
    marker="x",
    label="Flagged day",
)
ax.set(ylabel="Normalized power envelope", xlabel="Date")
ax.set_title("Telemetry-only health baseline")
ax.legend()
ax.grid(True, alpha=0.3)
fig.autofmt_xdate()
plt.show()
