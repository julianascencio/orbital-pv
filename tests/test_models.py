from datetime import UTC, datetime

from space_pv_core import PanelTelemetry


def test_panel_power() -> None:
    row = PanelTelemetry(datetime.now(UTC), "p1", 2.0, 0.5)
    assert row.power_w == 1.0
