"""与单元类型无关的方阵读取、校验和误差计算。"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


def read_square_matrix(path: Path, size: int) -> list[list[float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        matrix = [[float(cell) for cell in row] for row in csv.reader(handle) if row]
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise ValueError(f"矩阵尺寸不是 {size} x {size}：{path}")
    if not all(math.isfinite(value) for row in matrix for value in row):
        raise ValueError(f"矩阵包含非有限值：{path}")
    return matrix


def matrix_symmetry_error(matrix: list[list[float]]) -> float:
    numerator = 0.0
    denominator = 0.0
    for row, values in enumerate(matrix):
        for col, value in enumerate(values):
            difference = value - matrix[col][row]
            numerator += difference * difference
            denominator += value * value
    return math.sqrt(numerator) / math.sqrt(denominator) if denominator else math.sqrt(numerator)


def validate_reference_matrix(path: Path, size: int, symmetry_limit: float = 1.0e-10) -> list[list[float]]:
    matrix = read_square_matrix(path, size)
    scale = max(abs(value) for row in matrix for value in row)
    if scale <= 0.0 or matrix_symmetry_error(matrix) >= symmetry_limit:
        raise ValueError(f"参考矩阵为空或不对称：{path}")
    return matrix


def compare_matrices(actual: list[list[float]], expected: list[list[float]]) -> dict[str, float]:
    if len(actual) != len(expected) or any(len(row) != len(expected) for row in actual):
        raise ValueError("候选矩阵与参考矩阵尺寸不一致")
    difference = 0.0
    reference = 0.0
    max_absolute = 0.0
    max_relative = 0.0
    epsilon = 1.0e-12
    for row in range(len(expected)):
        for col in range(len(expected)):
            delta = actual[row][col] - expected[row][col]
            absolute = abs(delta)
            difference += delta * delta
            reference += expected[row][col] * expected[row][col]
            max_absolute = max(max_absolute, absolute)
            max_relative = max(max_relative, absolute / max(abs(expected[row][col]), epsilon))
    return {
        "frobenius_relative_error": math.sqrt(difference) / math.sqrt(reference) if reference else math.sqrt(difference),
        "max_absolute_error": max_absolute,
        "max_relative_entry_error": max_relative,
        "symmetry_error": matrix_symmetry_error(actual),
    }


def relative_block_error(
    actual: list[list[float]],
    expected: list[list[float]],
    rows: list[int],
    cols: list[int],
) -> float:
    difference = 0.0
    reference = 0.0
    for row in rows:
        for col in cols:
            delta = actual[row][col] - expected[row][col]
            difference += delta * delta
            reference += expected[row][col] * expected[row][col]
    return math.sqrt(difference) / math.sqrt(reference) if reference else math.sqrt(difference)


def matrix_diagnostics(
    actual: list[list[float]],
    expected: list[list[float]],
    groups: dict[str, list[int]],
    label,
) -> dict[str, Any]:
    block_errors = {
        f"{row_name}__{col_name}": relative_block_error(actual, expected, rows, cols)
        for row_name, rows in groups.items()
        for col_name, cols in groups.items()
    }
    entries: list[dict[str, Any]] = []
    for row in range(len(actual)):
        for col in range(len(actual)):
            delta = actual[row][col] - expected[row][col]
            entries.append(
                {
                    "row": label(row),
                    "col": label(col),
                    "actual": actual[row][col],
                    "expected": expected[row][col],
                    "difference": delta,
                    "absolute_difference": abs(delta),
                }
            )
    entries.sort(key=lambda item: item["absolute_difference"], reverse=True)
    return {"block_relative_errors": block_errors, "largest_absolute_entries": entries[:20]}
