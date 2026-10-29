import pandas as pd

from space_pv_connectors import load_birds_eps_workbook


def test_birds_calibrated_workbook_schema(tmp_path) -> None:
    path = tmp_path / "RAAVANA.xlsx"
    frame = pd.DataFrame(
        {
            "Time Stamp": [0, 5],
            "TPY (C)": [20.0, 21.0],
            "VPY (mV)": [2500.0, 2520.0],
            "IPY (mA)": [300.0, 310.0],
            "TPX (C)": [22.0, 23.0],
            "VPX (mV)": [2450.0, 2480.0],
            "IPX (mA)": [290.0, 295.0],
        }
    )
    with pd.ExcelWriter(path) as writer:
        frame.to_excel(writer, sheet_name="13 Feb 2021", index=False)

    result = load_birds_eps_workbook(path)

    assert set(result["panel_id"]) == {"+X", "+Y"}
    assert result["voltage_v"].max() < 3.0
    assert result["current_a"].max() < 1.0
    assert result["timestamp"].min() == pd.Timestamp("2021-02-13T00:00:00Z")
    assert result["timestamp"].max() == pd.Timestamp("2021-02-13T00:00:05Z")
