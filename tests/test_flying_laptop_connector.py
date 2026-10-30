import io
import json
import tarfile
from hashlib import md5, sha256
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from space_pv_connectors.flying_laptop import FlyingLaptopConnector, load_flying_laptop_power


def _packet() -> pd.DataFrame:
    """Packet-4900 schema with distinct calibrated V/I for every array."""
    frame = pd.DataFrame(
        {
            "timestamp": [1517443200000, 1517443230150, 1517443260300],
            "time": ["unused text time"] * 3,
            "PBTSOC03": [98.5, 98.4, 98.3],
        }
    )
    for index in range(4):
        frame[f"PSTCUR0{index}"] = [index + 0.1, index + 0.2, index + 0.3]
        frame[f"PSTVLT0{index}"] = [index + 20.0, index + 21.0, index + 22.0]
    return frame


def _archive(frame: pd.DataFrame, *, filename: str = "hk4900_2018-02.csv") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:bz2") as archive:
        for name, data in [
            (filename, frame.to_csv(sep="\t", index=False).encode()),
            ("../must_not_be_extracted.txt", b"unrelated telemetry"),
        ]:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return buffer.getvalue()


@pytest.fixture
def archive_path(tmp_path: Path) -> Path:
    path = tmp_path / "FLP_TM_HK_2018-02.tar.bz2"
    path.write_bytes(_archive(_packet()))
    return path


def test_physical_panel_mapping_epoch_milliseconds_and_source_metadata(archive_path: Path) -> None:
    result = load_flying_laptop_power(archive_path)

    assert len(result) == 12
    assert set(result["panel_id"]) == {"right", "left", "center", "test"}
    assert result["timestamp"].min() == pd.Timestamp("2018-02-01T00:00:00Z")
    assert result["timestamp"].max() == pd.Timestamp("2018-02-01T00:01:00.300Z")
    first = result.groupby("panel_id").first()
    assert first["voltage_v"].to_dict() == {
        "right": 20.0,
        "left": 21.0,
        "center": 22.0,
        "test": 23.0,
    }
    assert first["current_a"].to_dict() == {"right": 0.1, "left": 1.1, "center": 2.1, "test": 3.1}
    np.testing.assert_allclose(result["power_w"], result["voltage_v"] * result["current_a"])
    assert result.attrs["dataset_doi"] == "10.18419/darus-451"
    assert result.attrs["license"] == "CC BY 4.0"
    assert result.attrs["sha256"] == sha256(archive_path.read_bytes()).hexdigest()
    assert result.attrs["sensor_acquisition_delay_max_ms"] == 400
    assert not (archive_path.parent.parent / "must_not_be_extracted.txt").exists()


def test_time_filter_is_inclusive_exclusive_and_converts_timezone(archive_path: Path) -> None:
    result = load_flying_laptop_power(
        archive_path,
        time_min="2018-02-01T01:00:30.150+01:00",
        time_max="2018-02-01T00:01:00.300Z",
    )
    assert len(result) == 4
    assert set(result["timestamp"]) == {pd.Timestamp("2018-02-01T00:00:30.150Z")}
    assert load_flying_laptop_power(archive_path, time_min="2018-03-01").empty
    with pytest.raises(ValueError, match="earlier than"):
        load_flying_laptop_power(archive_path, time_min="2018-02-02", time_max="2018-02-01")


def test_missing_pair_omitted_without_clipping_signed_sensor_values(tmp_path: Path) -> None:
    frame = _packet()
    frame.loc[1, "PSTCUR00"] = np.nan
    frame.loc[2, "PSTVLT01"] = np.inf
    frame.loc[0, "PSTCUR03"] = -0.0000032
    path = tmp_path / "partial.tar.bz2"
    path.write_bytes(_archive(frame))

    result = load_flying_laptop_power(path)

    assert len(result) == 10
    assert result[result["panel_id"] == "test"]["current_a"].iloc[0] == pytest.approx(-0.0000032)
    assert result[result["panel_id"] == "test"]["power_w"].iloc[0] < 0


@pytest.mark.parametrize(
    ("frame", "filename", "message"),
    [
        (_packet().drop(columns="PSTCUR02"), "hk4900_2018-02.csv", "lacks columns"),
        (_packet().assign(timestamp="not a clock"), "hk4900_2018-02.csv", "no valid epoch"),
        (_packet(), "hk1901_2018-02.csv", "no packet 4900"),
    ],
)
def test_invalid_packet_schema_is_actionable(tmp_path: Path, frame, filename, message) -> None:
    path = tmp_path / "invalid.tar.bz2"
    path.write_bytes(_archive(frame, filename=filename))
    with pytest.raises(ValueError, match=message):
        load_flying_laptop_power(path)


def _mock_client(
    content: bytes, calls: list[httpx.Request], *, bad_checksum: bool = False
) -> httpx.Client:
    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.startswith("/api/datasets/"):
            assert request.url.params["persistentId"] == "doi:10.18419/darus-451"
            return httpx.Response(
                200,
                json={
                    "data": {
                        "latestVersion": {
                            "versionNumber": 9,
                            "versionMinorNumber": 0,
                            "files": [
                                {
                                    "dataFile": {
                                        "id": 264,
                                        "filename": "FLP_TM_HK_2018-02.tar.bz2",
                                        "checksum": {
                                            "type": "MD5",
                                            "value": "bad"
                                            if bad_checksum
                                            else md5(content, usedforsecurity=False).hexdigest(),
                                        },
                                    }
                                }
                            ],
                        }
                    }
                },
            )
        assert request.url.path == "/api/access/datafile/264"
        return httpx.Response(200, content=content)

    return httpx.Client(transport=httpx.MockTransport(respond))


def test_download_provenance_and_offline_cache_validation(tmp_path: Path) -> None:
    path = tmp_path / "cached.tar.bz2"
    content = _archive(_packet())
    calls: list[httpx.Request] = []
    with FlyingLaptopConnector() as connector:
        connector._client.close()
        connector._client = _mock_client(content, calls)
        result = connector.download_frame("2018-02", path, time_max="2018-02-01T00:00:31Z")
    assert len(calls) == 2
    assert len(result) == 8
    assert result.attrs["url"] == "https://darus.uni-stuttgart.de/api/access/datafile/264"
    assert result.attrs["dataset_version"] == "9.0"
    assert len(load_flying_laptop_power(path)) == 12
    assert len(calls) == 2  # Local cache loading performs no HTTP request.
    sidecar = path.with_name(path.name + ".provenance.json")
    metadata = json.loads(sidecar.read_text())
    metadata["sha256"] = "modified"
    sidecar.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="provenance checksum"):
        load_flying_laptop_power(path)


@pytest.mark.parametrize("month", ["2018-2", "2018-13", "../2018-02", "not-a-month"])
def test_bad_month_rejected_before_network(tmp_path: Path, month: str) -> None:
    calls: list[httpx.Request] = []
    with FlyingLaptopConnector() as connector:
        connector._client.close()
        connector._client = _mock_client(_archive(_packet()), calls)
        with pytest.raises(ValueError, match="month"):
            connector.download_month(month, tmp_path / "unused")
    assert not calls


def test_unavailable_month_and_corrupt_download_not_written(tmp_path: Path) -> None:
    path = tmp_path / "missing.tar.bz2"
    calls: list[httpx.Request] = []
    with FlyingLaptopConnector() as connector:
        connector._client.close()
        connector._client = _mock_client(_archive(_packet()), calls, bad_checksum=True)
        with pytest.raises(LookupError, match="No unique"):
            connector.download_month("2018-03", path)
        with pytest.raises(ValueError, match="catalog checksum"):
            connector.download_month("2018-02", path)
    assert not path.exists()
