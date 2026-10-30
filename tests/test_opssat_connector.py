from hashlib import sha256
from io import StringIO
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from space_pv_connectors.opssat import OpsSatADConnector, load_opssat_segments


@pytest.fixture
def source_frame() -> pd.DataFrame:
    # Match the published CSV, including its misleading all-"anomaly" text
    # label. Two independent source segments deliberately overlap in UTC.
    return pd.DataFrame(
        {
            "channel": ["CADC0892"] * 4 + ["CADC0872"],
            "timestamp": [
                "2022-01-04T20:00:50.000Z",
                "2022-01-04T20:00:51.000Z",
                "2022-01-04T20:00:50.000Z",
                "2022-01-04T20:00:55.000Z",
                "2022-01-04T20:00:50.000Z",
            ],
            "value": [0.1, 0.2, 1.0, 1.1, -2.1487e-5],
            "label": ["anomaly"] * 5,
            "sampling": [1, 1, 5, 5, 1],
            "anomaly": [0, 0, 1, 1, 0],
            "segment": [17, 17, 18, 18, 19],
            "train": [1, 1, 0, 0, 1],
        }
    )


def write_csv(tmp_path: Path, frame: pd.DataFrame) -> Path:
    path = tmp_path / "segments.csv"
    frame.to_csv(path, index=False)
    return path


def test_original_values_utc_annotations_and_segment_boundaries(
    tmp_path: Path,
    source_frame: pd.DataFrame,
) -> None:
    result = load_opssat_segments(write_csv(tmp_path, source_frame))

    assert len(result) == 5
    assert str(result["timestamp"].dt.tz) == "UTC"
    assert result["timestamp"].min() == pd.Timestamp("2022-01-04T20:00:50Z")
    assert result["segment"].nunique() == 3
    assert set(result["label"]) == {"anomaly"}
    assert result.loc[result["segment"].eq(17), "anomaly"].eq(0).all()
    assert result.loc[result["segment"].eq(18), "anomaly"].eq(1).all()
    pd.testing.assert_series_equal(
        result.sort_values(["segment", "timestamp"])["value"].reset_index(drop=True),
        source_frame["value"],
    )
    same_time = result[
        result["channel"].eq("CADC0892") & result["timestamp"].eq(result["timestamp"].min())
    ]
    assert set(same_time["segment"]) == {17, 18}
    assert set(result["value_unit"]) == {"unspecified_source_unit"}
    assert result.loc[result["channel"].eq("CADC0892"), "channel_name"].eq("I_PD5_THETA").all()
    assert result.attrs["source_doi"] == "10.5281/zenodo.15108715"
    assert not result.attrs["matches_complete_release"]


def test_missing_values_remain_missing_and_no_numeric_fill_value_is_invented(
    tmp_path: Path,
    source_frame: pd.DataFrame,
) -> None:
    source_frame.loc[0, "value"] = np.nan
    source_frame.loc[1, "value"] = np.inf
    source_frame.loc[2, "value"] = -9999.0
    result = load_opssat_segments(write_csv(tmp_path, source_frame))

    assert len(result) == len(source_frame)
    assert result["is_valid_value"].sum() == 3
    assert result["value"].isna().sum() == 1
    assert np.isinf(result["value"]).sum() == 1
    # There is no documented magic fill number in this source: do not quietly
    # discard measured negative values or apply another provider's conventions.
    assert result.loc[result["value"].eq(-9999.0), "is_valid_value"].all()


def test_channel_and_fixed_split_filters(tmp_path: Path, source_frame: pd.DataFrame) -> None:
    result = load_opssat_segments(
        write_csv(tmp_path, source_frame), channels=["CADC0892"], split="test"
    )
    assert len(result) == 2
    assert set(result["segment"]) == {18}
    assert result["train"].eq(0).all()
    assert result["sampling"].eq(5).all()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("timestamp", "not-a-time", "invalid source timestamps"),
        ("anomaly", 2, "anomaly must contain only 0 or 1"),
        ("train", -1, "train must contain only 0 or 1"),
        ("sampling", 0, "sampling periods must be finite and positive"),
        ("segment", 1.5, "segment IDs must be positive integers"),
        ("channel", "UNKNOWN", "unknown or missing channel IDs"),
    ],
)
def test_invalid_source_metadata_is_rejected(
    tmp_path: Path,
    source_frame: pd.DataFrame,
    field: str,
    value: object,
    message: str,
) -> None:
    source_frame[field] = source_frame[field].astype(object)
    source_frame.loc[0, field] = value
    with pytest.raises(ValueError, match=message):
        load_opssat_segments(write_csv(tmp_path, source_frame))


def test_feature_table_is_not_misread_as_original_telemetry(tmp_path: Path) -> None:
    frame = pd.DataFrame({"segment": [1], "mean": [0.2], "anomaly": [0], "train": [1]})
    with pytest.raises(ValueError, match="Missing OPS-SAT telemetry columns"):
        load_opssat_segments(write_csv(tmp_path, frame))


def test_conflicting_labels_within_one_source_segment_are_rejected(
    tmp_path: Path,
    source_frame: pd.DataFrame,
) -> None:
    source_frame.loc[1, "anomaly"] = 1
    with pytest.raises(ValueError, match="metadata must be constant"):
        load_opssat_segments(write_csv(tmp_path, source_frame))


def test_bad_filters_are_rejected_before_network_access(tmp_path: Path) -> None:
    with OpsSatADConnector() as connector:
        with pytest.raises(ValueError, match="Unknown OPS-SAT channels"):
            connector.download_frame(tmp_path / "unused.csv", channels=["UNKNOWN"])
        with pytest.raises(ValueError, match="split must be"):
            connector.download_frame(tmp_path / "unused.csv", split="validation")
        with pytest.raises(ValueError, match="nonempty sequence"):
            connector.download_frame(tmp_path / "unused.csv", channels="CADC0892")


def test_verified_download_cache_and_original_provenance(
    tmp_path: Path,
    source_frame: pd.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer = StringIO()
    source_frame.to_csv(buffer, index=False)
    payload = buffer.getvalue().encode()
    checksum = sha256(payload).hexdigest()
    monkeypatch.setattr(OpsSatADConnector, "SHA256", checksum)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=payload)

    path = tmp_path / "cache" / "segments.csv"
    with OpsSatADConnector() as connector:
        connector._client.close()
        connector._client = httpx.Client(transport=httpx.MockTransport(handler))
        first = connector.download_frame(path)
        second = connector.download_frame(path, channels=["CADC0892"], split="test")

    assert calls == [OpsSatADConnector.URL]
    assert path.read_bytes() == payload
    assert first.attrs["matches_complete_release"]
    assert len(second) == 2
    receipt = first.attrs["download_receipt"]
    assert receipt == second.attrs["download_receipt"]
    assert receipt["sha256"] == checksum
    assert receipt["bytes"] == len(payload)
    assert receipt["url"] == OpsSatADConnector.URL
    assert receipt["dataset_doi"] == OpsSatADConnector.DATASET_DOI
    assert receipt["license"] == "CC-BY-4.0"
    assert receipt["retrieved_at"]
    assert path.with_suffix(".csv.provenance.json").exists()


def test_unexpected_response_preserves_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "segments.csv"
    path.write_bytes(b"existing user data")
    with OpsSatADConnector() as connector:
        connector._client.close()
        connector._client = httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"not csv"))
        )
        with pytest.raises(ValueError, match="checksum does not match"):
            connector.download_frame(path, refresh=True)
    assert path.read_bytes() == b"existing user data"
    assert not path.with_suffix(".csv.provenance.json").exists()


def test_unverified_cache_is_not_silently_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "segments.csv"
    path.write_bytes(b"unverified local data")

    def unexpected_request(request: httpx.Request) -> httpx.Response:
        pytest.fail(f"Unexpected HTTP request: {request.url}")

    with OpsSatADConnector() as connector:
        connector._client.close()
        connector._client = httpx.Client(transport=httpx.MockTransport(unexpected_request))
        with pytest.raises(ValueError, match="checksum does not match"):
            connector.download_frame(path)
    assert path.read_bytes() == b"unverified local data"
