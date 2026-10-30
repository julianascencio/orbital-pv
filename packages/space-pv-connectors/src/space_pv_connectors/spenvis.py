"""Read the documented SPENVIS/UNIRAD block-structured CSV interchange format.

This is an importer for user-exported results, not a SPENVIS or IRENE service
client. Model configuration, statistical confidence, shielding, energy-bin
meaning and units are preserved rather than inferred from a filename.

Specification: https://space-env.esa.int/Manuals/Mulassis/ml-v02-00/OutputFiles.html
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class SpenvisVariable:
    name: str
    units: str
    dimension: int
    title: str
    metadata_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class SpenvisBlock:
    comments: tuple[str, ...]
    metadata: dict[str, dict[str, Any]]
    annotations: tuple[str, ...]
    variables: tuple[SpenvisVariable, ...]
    data: pd.DataFrame
    footer: str
    following_blocks: int


def _record(line: str, number: int) -> list[str]:
    try:
        return [
            value.strip()
            for value in next(
                csv.reader(
                    [line],
                    delimiter=",",
                    quotechar="'",
                    skipinitialspace=True,
                    strict=True,
                )
            )
        ]
    except (csv.Error, StopIteration) as exc:
        raise ValueError(f"Malformed SPENVIS record at line {number}") from exc


def _real(value: str) -> float:
    return float(value.replace("D", "E").replace("d", "e"))


def parse_spenvis(text: str) -> list[SpenvisBlock]:
    """Parse scalar/vector variables, metadata, annotations and multiple blocks.

    Vector elements become ``NAME[0]``, ``NAME[1]``, etc. Their energy/coordinate
    association remains in ``metadata`` and must be selected explicitly. Units
    are retained verbatim in each variable and in ``data.attrs['units']``.
    Truncated records, inconsistent column/header counts, duplicate names, and
    provider error footers raise ``ValueError``. FORTRAN D exponents are supported.
    """
    lines = text.lstrip("\ufeff").splitlines()
    blocks: list[SpenvisBlock] = []
    offset = 0
    while offset < len(lines):
        if not lines[offset].strip():
            offset += 1
            continue
        header_line = offset + 1
        fields = _record(lines[offset], header_line)
        if len(fields) != 9 or fields[0] != "*":
            raise ValueError(f"Expected SPENVIS block header at line {header_line}")
        try:
            nh, nc, nm, na, nv, nd, nl, nb = map(int, fields[1:])
        except ValueError as exc:
            raise ValueError(f"Noninteger block header at line {header_line}") from exc
        if min(nc, nm, na, nb) < 0 or nv < 1 or nd < 1 or nl < -1 or nh != 1 + nc + nm + na + nv:
            raise ValueError(f"Inconsistent SPENVIS header at line {header_line}")
        if offset + nh >= len(lines):
            raise ValueError("Truncated SPENVIS header or missing data footer")
        offset += 1
        comments = []
        for _ in range(nc):
            record = _record(lines[offset], offset + 1)
            if len(record) != 1:
                raise ValueError(f"Invalid comment at line {offset + 1}")
            comments.append(record[0])
            offset += 1
        metadata: dict[str, dict[str, Any]] = {}
        for _ in range(nm):
            record = _record(lines[offset], offset + 1)
            try:
                name, kind = record[0], int(record[1])
                count = 1 if kind < 0 else kind
                if (
                    not name
                    or name in metadata
                    or count < 1
                    or len(record) not in {2 + count, 3 + count}
                ):
                    raise ValueError("Invalid metadata width or name")
                values = record[2 : 2 + count]
                metadata[name] = {
                    "values": values[0] if kind < 0 else tuple(_real(value) for value in values),
                    "units": record[-1] if len(record) == 3 + count else None,
                }
            except (IndexError, ValueError) as exc:
                raise ValueError(f"Invalid SPENVIS metadata at line {offset + 1}") from exc
            offset += 1
        annotations = tuple(lines[offset : offset + na])
        offset += na
        variables = []
        columns: list[str] = []
        units: dict[str, str] = {}
        for _ in range(nv):
            record = _record(lines[offset], offset + 1)
            try:
                name, unit, dimension, title = record[:4]
                size = int(dimension)
                if not name or size < 1:
                    raise ValueError("Invalid variable name or dimension")
                new_columns = [name] if size == 1 else [f"{name}[{index}]" for index in range(size)]
                if any(column in units for column in new_columns):
                    raise ValueError("Duplicate variable columns")
                columns.extend(new_columns)
                units.update(dict.fromkeys(new_columns, unit))
                variables.append(SpenvisVariable(name, unit, size, title, tuple(record[4:])))
            except ValueError as exc:
                raise ValueError(f"Invalid SPENVIS variable at line {offset + 1}") from exc
            offset += 1
        if len(columns) != nd:
            raise ValueError("SPENVIS variable dimensions disagree with declared data columns")
        rows = []
        footer = None
        while offset < len(lines):
            record = _record(lines[offset], offset + 1)
            if lines[offset].lstrip().startswith("'"):
                if len(record) != 1 or record[0] == "*":
                    raise ValueError("Missing SPENVIS footer before next block")
                footer = record[0]
                offset += 1
                break
            if len(record) != nd:
                raise ValueError(f"SPENVIS data width mismatch at line {offset + 1}")
            try:
                rows.append([_real(value) for value in record])
            except ValueError as exc:
                raise ValueError(f"Invalid SPENVIS numeric data at line {offset + 1}") from exc
            offset += 1
        if footer is None or (nl >= 0 and len(rows) != nl):
            raise ValueError("Truncated SPENVIS block or declared data row count mismatch")
        if footer.strip("* ").upper().startswith("ERROR"):
            raise ValueError(f"SPENVIS provider reported: {footer}")
        frame = pd.DataFrame(rows, columns=columns, dtype=float)
        frame.attrs.update(
            {
                "units": units,
                "metadata": metadata,
                "comments": tuple(comments),
                "source_format": "SPENVIS/UNIRAD CSV",
                "units_converted": False,
            }
        )
        blocks.append(
            SpenvisBlock(
                tuple(comments), metadata, annotations, tuple(variables), frame, footer, nb
            )
        )
    if not blocks:
        raise ValueError("No SPENVIS blocks found")
    for index, block in enumerate(blocks):
        if block.following_blocks > len(blocks) - index - 1:
            raise ValueError("Truncated SPENVIS section: declared following blocks are missing")
    return blocks


def read_spenvis(path: str | Path, *, max_bytes: int = 128 * 1024 * 1024) -> list[SpenvisBlock]:
    """Read a local export and attach its checksum to each returned data frame."""
    source = Path(path)
    if max_bytes <= 0 or source.stat().st_size > max_bytes:
        raise ValueError("SPENVIS file exceeds max_bytes")
    content = source.read_bytes()
    blocks = parse_spenvis(content.decode("utf-8-sig"))
    for block in blocks:
        block.data.attrs["source_file_sha256"] = hashlib.sha256(content).hexdigest()
    return blocks
