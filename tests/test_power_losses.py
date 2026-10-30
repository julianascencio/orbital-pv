"""Independent accounting and observation-support checks for the public loss API."""

import numpy as np
import pandas as pd
import pytest

import orbitalpv as opv


def measurements(seconds, expected, actual, **columns):
    return pd.DataFrame(
        {
            "timestamp": pd.Timestamp("2026-01-01", tz="UTC") + pd.to_timedelta(seconds, unit="s"),
            "expected_power_w": expected,
            "actual_power_w": actual,
            **columns,
        }
    )


def test_ordered_losses_close_and_bucket_interacting_factors() -> None:
    frame = measurements([0, 1800, 3600], 100.0, 76.0, mismatch=90.0, wiring=81.0)
    stages = [
        opv.LossStage("mismatch", "mismatch", "electrical", "Calibrated string model"),
        opv.LossStage("wiring", "wiring", "electrical", "Harness resistance measurements"),
    ]
    result = opv.power_loss_breakdown(frame, stages)
    np.testing.assert_allclose(result.components_w["mismatch"], 10.0)
    np.testing.assert_allclose(result.components_w["wiring"], 9.0)
    np.testing.assert_allclose(result.categories_w["electrical"], 19.0)
    np.testing.assert_allclose(result.components_w["unexplained"], 5.0)
    np.testing.assert_allclose(result.components_w.sum(axis=1), result.samples["total_loss_w"])
    summary = opv.summarize_power_losses(result, max_gap_s=1800)
    total = summary.totals.iloc[0]
    assert total["gap_energy_wh"] == pytest.approx(24.0)
    assert total["attributed_energy_wh"] == pytest.approx(19.0)
    assert total["unexplained_energy_wh"] == pytest.approx(5.0)
    assert total["expected_energy_wh"] - total["actual_energy_wh"] == pytest.approx(24.0)
    assert summary.components["net_loss_wh"].sum() == pytest.approx(24.0)
    assert summary.categories["net_loss_wh"].sum() == pytest.approx(24.0)
    assert summary.categories["percent_expected"].sum() == pytest.approx(24.0)
    assert summary.components.set_index("component").loc["wiring", "evidence"] == stages[1].evidence


def test_gains_and_negative_sensor_offsets_are_preserved() -> None:
    frame = measurements([0, 60], [100.0, 0.0], [112.0, -0.001], cold=[110.0, 0.0])
    result = opv.power_loss_breakdown(
        frame, [opv.LossStage("temperature", "cold", "temperature", "Measured cell temperature")]
    )
    np.testing.assert_allclose(result.components_w["temperature"], [-10.0, 0.0])
    np.testing.assert_allclose(result.components_w["unexplained"], [-2.0, 0.001])
    np.testing.assert_allclose(result.samples["total_loss_w"], [-12.0, 0.001])


def test_no_evidence_leaves_entire_gap_unexplained() -> None:
    result = opv.power_loss_breakdown(measurements([0, 3600], 100.0, 80.0))
    assert list(result.components_w) == ["unexplained"]
    np.testing.assert_array_equal(result.samples["attributed_loss_w"], 0.0)
    summary = opv.summarize_power_losses(result, max_gap_s=3600)
    assert list(summary.categories["category"]) == ["unexplained"]
    assert summary.categories.iloc[0]["net_loss_wh"] == pytest.approx(20.0)


def test_irregular_sampling_uses_elapsed_time_not_sample_mean() -> None:
    result = opv.power_loss_breakdown(
        measurements([0, 1800, 7200], [100.0, 200.0, 100.0], [80.0, 150.0, 50.0])
    )
    total = opv.summarize_power_losses(result, max_gap_s=5400).totals.iloc[0]
    assert total["expected_energy_wh"] == pytest.approx(300.0)
    assert total["actual_energy_wh"] == pytest.approx(207.5)
    assert total["gap_energy_wh"] == pytest.approx(92.5)
    assert total["observed_duration_h"] == 2.0
    assert total["coverage_fraction"] == 1.0


def test_positive_and_negative_energies_split_at_zero_crossing() -> None:
    result = opv.power_loss_breakdown(measurements([0, 3600], 4.0, [2.0, 6.0]))
    summary = opv.summarize_power_losses(result, max_gap_s=3600)
    total = summary.totals.iloc[0]
    assert total["gap_energy_wh"] == pytest.approx(0.0)
    # Two triangles, each base 0.5 h and height 2 W, not endpoint-clipped trapezoids.
    assert total["positive_gap_energy_wh"] == pytest.approx(0.5)
    assert total["surplus_energy_wh"] == pytest.approx(0.5)
    assert summary.components.iloc[0]["loss_wh"] == pytest.approx(0.5)
    assert summary.components.iloc[0]["gain_wh"] == pytest.approx(0.5)


def test_category_gross_energies_account_for_simultaneous_cancellation() -> None:
    frame = measurements([0, 3600], 100.0, 100.0, a=90.0, b=100.0)
    result = opv.power_loss_breakdown(
        frame,
        [
            opv.LossStage("first", "a", "optical", "First specified correction"),
            opv.LossStage("second", "b", "optical", "Second specified correction"),
        ],
    )
    summary = opv.summarize_power_losses(result, max_gap_s=3600)
    assert summary.components["loss_wh"].sum() == pytest.approx(10.0)
    assert summary.components["gain_wh"].sum() == pytest.approx(10.0)
    assert summary.categories["loss_wh"].sum() == pytest.approx(0.0)
    assert summary.categories["gain_wh"].sum() == pytest.approx(0.0)


def test_common_support_keeps_nans_and_excludes_long_gaps() -> None:
    frame = measurements(
        [0, 30, 60, 90, 300, 330, 360],
        100.0,
        [80.0, 80.0, np.nan, 80.0, 80.0, 80.0, 80.0],
        stage=[90.0, 90.0, 90.0, 90.0, 90.0, np.nan, 90.0],
    )
    result = opv.power_loss_breakdown(
        frame, [opv.LossStage("wiring", "stage", "electrical", "Supplied harness model")]
    )
    assert len(result.samples) == 7
    assert result.samples.loc[[2, 5], "valid"].eq(False).all()
    assert result.components_w.loc[[2, 5]].isna().all().all()
    assert result.categories_w.loc[[2, 5]].isna().all().all()
    total = opv.summarize_power_losses(result, max_gap_s=30).totals.iloc[0]
    assert total["valid_intervals"] == 1
    assert total["total_intervals"] == 6
    assert total["valid_samples"] == 5
    assert total["observed_duration_h"] == pytest.approx(30.0 / 3600.0)
    assert total["window_duration_h"] == pytest.approx(0.1)
    assert total["coverage_fraction"] == pytest.approx(1.0 / 12.0)
    assert total["expected_energy_wh"] == pytest.approx(100.0 / 120.0)
    assert total["gap_energy_wh"] == pytest.approx(20.0 / 120.0)


def test_multiple_panels_are_sorted_and_integrated_independently() -> None:
    a = measurements([0, 3600], 100.0, 90.0, panel_id="A")
    b = measurements([0, 1800], 200.0, 160.0, panel_id="B")
    frame = pd.concat([b.iloc[[1]], a.iloc[[1]], b.iloc[[0]], a.iloc[[0]]])
    original = frame.copy(deep=True)
    result = opv.power_loss_breakdown(frame, group_columns=("panel_id",))
    pd.testing.assert_frame_equal(frame, original)
    summary = opv.summarize_power_losses(result, max_gap_s=3600)
    totals = summary.totals.set_index("panel_id")
    assert totals.loc["A", "gap_energy_wh"] == pytest.approx(10.0)
    assert totals.loc["B", "gap_energy_wh"] == pytest.approx(20.0)
    assert totals.loc["A", "observed_duration_h"] == 1.0
    assert totals.loc["B", "observed_duration_h"] == 0.5
    assert list(summary.components["panel_id"]) == ["A", "B"]


def test_two_group_columns_and_custom_input_names() -> None:
    frame = measurements([0, 3600], 100.0, 95.0, spacecraft="one", panel="A").rename(
        columns={"timestamp": "time", "expected_power_w": "forecast", "actual_power_w": "measured"}
    )
    result = opv.power_loss_breakdown(
        frame,
        expected_power_column="forecast",
        actual_power_column="measured",
        timestamp_column="time",
        group_columns=("spacecraft", "panel"),
    )
    total = opv.summarize_power_losses(result, max_gap_s=3600).totals.iloc[0]
    assert total["spacecraft"] == "one" and total["panel"] == "A"
    assert total["gap_energy_wh"] == pytest.approx(5.0)


@pytest.mark.parametrize(
    "seconds,actual", [([0], [80.0]), ([0, 60], [np.nan, 80.0]), ([0, 61], [80.0, 80.0])]
)
def test_no_usable_intervals_means_unknown_energy_not_zero(seconds, actual) -> None:
    summary = opv.summarize_power_losses(
        opv.power_loss_breakdown(measurements(seconds, 100.0, actual)), max_gap_s=60
    )
    total = summary.totals.iloc[0]
    assert np.isnan(total["expected_energy_wh"])
    assert np.isnan(total["actual_energy_wh"])
    assert np.isnan(total["gap_energy_wh"])
    assert total["observed_duration_h"] == 0.0
    assert total["valid_intervals"] == 0
    assert summary.categories["net_loss_wh"].isna().all()


def test_zero_expected_energy_has_no_percentage_and_keeps_gain() -> None:
    summary = opv.summarize_power_losses(
        opv.power_loss_breakdown(measurements([0, 3600], 0.0, 1.0)), max_gap_s=3600
    )
    assert summary.totals.iloc[0]["gap_energy_wh"] == pytest.approx(-1.0)
    assert summary.components.iloc[0]["gain_wh"] == pytest.approx(1.0)
    assert summary.components["percent_expected"].isna().all()


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "unexplained"),
        ("name", "two words"),
        ("power_column", ""),
        ("category", "soiling"),
        ("category", "unexplained"),
        ("evidence", " "),
    ],
)
def test_stages_require_valid_names_categories_and_evidence(field, value) -> None:
    fields = dict(
        name="harness", power_column="after", category="electrical", evidence="Calibration"
    )
    fields[field] = value
    with pytest.raises(ValueError):
        opv.LossStage(**fields)


@pytest.mark.parametrize(
    "column,value",
    [
        ("expected_power_w", -1.0),
        ("expected_power_w", np.inf),
        ("actual_power_w", -np.inf),
        ("stage", -1.0),
    ],
)
def test_invalid_power_inputs_are_rejected(column, value) -> None:
    frame = measurements([0, 60], 100.0, 80.0, stage=90.0)
    frame.loc[0, column] = value
    with pytest.raises(ValueError):
        opv.power_loss_breakdown(
            frame, [opv.LossStage("harness", "stage", "electrical", "Calibration")]
        )


@pytest.mark.parametrize("column", ["expected_power_w", "actual_power_w", "stage"])
def test_complex_powers_are_rejected_without_discarding_imaginary_part(column) -> None:
    frame = measurements([0, 60], 100.0, 80.0, stage=90.0)
    frame[column] = [100.0 + 40.0j, 100.0 + 40.0j]
    with pytest.raises(ValueError, match="real values"):
        opv.power_loss_breakdown(
            frame, [opv.LossStage("harness", "stage", "electrical", "Calibration")]
        )


def test_duplicate_and_missing_timestamps_or_identifiers_are_rejected() -> None:
    frame = measurements([0, 0], 100.0, 80.0)
    with pytest.raises(ValueError, match="Duplicate"):
        opv.power_loss_breakdown(frame)
    frame = measurements([0, 60], 100.0, 80.0, panel_id=["A", None])
    with pytest.raises(ValueError, match="cannot be missing"):
        opv.power_loss_breakdown(frame, group_columns=("panel_id",))
    frame = measurements([0, 60], 100.0, 80.0)
    frame.loc[0, "timestamp"] = pd.NaT
    with pytest.raises(ValueError, match="cannot be missing"):
        opv.power_loss_breakdown(frame)


def test_ambiguous_stage_or_group_specifications_are_rejected() -> None:
    frame = measurements([0, 60], 100.0, 80.0, stage=90.0)
    stage = opv.LossStage("harness", "stage", "electrical", "Calibration")
    with pytest.raises(ValueError, match="unique"):
        opv.power_loss_breakdown(frame, [stage, stage])
    with pytest.raises(ValueError, match="not a string"):
        opv.power_loss_breakdown(frame, group_columns="panel_id")
    with pytest.raises(ValueError, match="reserved"):
        opv.power_loss_breakdown(frame, group_columns=("expected_power_w",))
    with pytest.raises(ValueError, match="Missing required"):
        opv.power_loss_breakdown(frame.drop(columns="actual_power_w"))
    with pytest.raises(ValueError, match="at least one"):
        opv.power_loss_breakdown(frame.iloc[:0])


@pytest.mark.parametrize("max_gap_s", [0.0, -1.0, np.inf, np.nan])
def test_energy_cutoff_must_be_positive_finite(max_gap_s) -> None:
    result = opv.power_loss_breakdown(measurements([0, 60], 100.0, 80.0))
    with pytest.raises(ValueError, match="max_gap_s"):
        opv.summarize_power_losses(result, max_gap_s=max_gap_s)
