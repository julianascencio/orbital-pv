from pathlib import Path

import pandas as pd
import pytest

import orbitalpv as opv
from space_pv_connectors import BirdsEPSConnector, load_birds_eps_workbook
from space_pv_connectors.http_base import DownloadReceipt


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
    assert result["elapsed_seconds"].tolist() == [0, 5, 0, 5]
    assert set(result["campaign_date"]) == {pd.Timestamp("2021-02-13T00:00:00Z")}
    assert set(result["timestamp_basis"]) == {"campaign_date_midnight_plus_elapsed_seconds"}
    assert set(result["campaign_date_basis"]) == {"sheet_date"}


def _calibrated_frame(elapsed: list[float | None]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Time stamp": elapsed,
            "Tpy (°C)": 20.0,
            "Vpy (mV)": 2500.0,
            "Ipy (mA)": 300.0,
            "Tpx (°C)": 21.0,
            "Vpx (mV)": 2400.0,
            "Ipx (mA)": 250.0,
        }
    )


@pytest.fixture
def tsuru_workbook(tmp_path: Path) -> Path:
    path = tmp_path / "TSURU.xlsx"
    # Source sheets are not chronological, some omit years, and undated tests
    # must never be interpreted as additional on-orbit campaigns.
    with pd.ExcelWriter(path) as writer:
        for sheet in ["January 02 2022", "May 06", "March 28", "Test1 w batt", "Test2 wo batt"]:
            _calibrated_frame([0.0, 11.3]).to_excel(writer, sheet_name=sheet, index=False)
    return path


def test_yearless_campaign_dates_and_explicit_next_year(tsuru_workbook: Path) -> None:
    result = opv.load_birds_eps_workbook(tsuru_workbook, campaign_year=2021)

    assert len(result) == 12
    dates = result.groupby("source_sheet")["campaign_date"].first().to_dict()
    assert dates == {
        "March 28": pd.Timestamp("2021-03-28T00:00:00Z"),
        "May 06": pd.Timestamp("2021-05-06T00:00:00Z"),
        "January 02 2022": pd.Timestamp("2022-01-02T00:00:00Z"),
    }
    assert result.groupby("source_sheet")["campaign_date_basis"].first().to_dict() == {
        "March 28": "explicit_campaign_year",
        "May 06": "explicit_campaign_year",
        "January 02 2022": "sheet_date",
    }
    for _, panel in result.groupby("panel_id"):
        assert panel["timestamp"].is_monotonic_increasing
        assert panel["source_sheet"].drop_duplicates().tolist() == [
            "March 28",
            "May 06",
            "January 02 2022",
        ]


def test_missing_campaign_year_does_not_return_only_fully_dated_sheets(
    tsuru_workbook: Path,
) -> None:
    with pytest.raises(ValueError, match="omits its year; pass campaign_year explicitly"):
        load_birds_eps_workbook(tsuru_workbook)


def test_raw_workbook_retains_test_sheets_and_needs_no_campaign_year(
    tsuru_workbook: Path,
) -> None:
    raw = load_birds_eps_workbook(tsuru_workbook, normalized=False)

    assert len(raw) == 10
    assert set(raw["source_sheet"]) == {
        "January 02 2022",
        "May 06",
        "March 28",
        "Test1 w batt",
        "Test2 wo batt",
    }
    assert "timestamp" not in raw


def test_elapsed_clock_survives_footer_rows_and_preserves_fractional_seconds(
    tmp_path: Path,
) -> None:
    path = tmp_path / "with_footer.xlsx"
    # Most rows in some upstream sheets have calibration values but no time.
    # They must neither hide the usable rows nor force epoch-nanosecond parsing.
    frame = _calibrated_frame([0.0, 11.3, 22.6, *([None] * 8)])
    with pd.ExcelWriter(path) as writer:
        frame.to_excel(writer, sheet_name="March 28", index=False)

    result = load_birds_eps_workbook(path, campaign_year=2021)

    assert len(result) == 6
    assert result["elapsed_seconds"].notna().all()
    for _, panel in result.groupby("panel_id"):
        assert panel["elapsed_seconds"].tolist() == [0.0, 11.3, 22.6]
        assert panel["timestamp"].tolist() == [
            pd.Timestamp("2021-03-28T00:00:00Z"),
            pd.Timestamp("2021-03-28T00:00:11.3Z"),
            pd.Timestamp("2021-03-28T00:00:22.6Z"),
        ]


def test_unrecognized_campaign_date_cannot_become_epoch_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "unknown_date.xlsx"
    with pd.ExcelWriter(path) as writer:
        _calibrated_frame([0.0, 5.0]).to_excel(writer, sheet_name="Undated", index=False)

    with pytest.raises(ValueError, match="no recognizable date"):
        load_birds_eps_workbook(path, campaign_year=2021)


def test_public_fetch_forwards_campaign_year_through_connector(
    tsuru_workbook: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def downloaded(
        self: BirdsEPSConnector, satellite: str, destination: str | Path
    ) -> DownloadReceipt:
        assert satellite == "TSURU"
        assert Path(destination) == tsuru_workbook
        return self.receipt(
            "BIRDS EPS",
            "https://example.org/TSURU.xlsx",
            tsuru_workbook.read_bytes(),
            path=tsuru_workbook,
        )

    monkeypatch.setattr(BirdsEPSConnector, "download", downloaded)
    result = opv.fetch_birds_eps("TSURU", tsuru_workbook, campaign_year=2021)

    assert result["source_sheet"].nunique() == 3
    assert result["campaign_date"].min() == pd.Timestamp("2021-03-28T00:00:00Z")
    assert opv.load_birds_eps_workbook is load_birds_eps_workbook
