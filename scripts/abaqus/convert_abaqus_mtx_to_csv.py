#!/usr/bin/env python3
"""将 Abaqus 刚度 .mtx 文件转换为项目使用的 24 x 24 CSV 格式。

支持两种数值行格式：
- 行号, 列号, 数值
- 节点i, 自由度i, 节点j, 自由度j, 数值

第二种格式适用于 Abaqus 坐标矩阵输出，因为它保留了节点和自由度标签。
脚本会自动补齐非对角项，使矩阵保持对称。
"""

from __future__ import annotations

import csv
import glob
import re
import sys
from pathlib import Path


NODE_ORDER = [1, 2, 3, 4]
DOF_ORDER = [1, 2, 3, 4, 5, 6]
SIZE = len(NODE_ORDER) * len(DOF_ORDER)


def dof_index(node: int, dof: int) -> int:
    try:
        node_offset = NODE_ORDER.index(node)
        dof_offset = DOF_ORDER.index(dof)
    except ValueError as exc:
        raise ValueError(f"unexpected node/dof label in Abaqus matrix: node={node}, dof={dof}") from exc
    return node_offset * len(DOF_ORDER) + dof_offset


def parse_numbers(line: str) -> list[float]:
    cleaned = line.strip()
    if not cleaned or cleaned.startswith("*") or cleaned.startswith("**"):
        return []
    return [float(item) for item in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?", cleaned.replace("D", "E"))]


def add_entry(matrix: list[list[float]], row: int, col: int, value: float) -> None:
    matrix[row][col] += value
    if row != col:
        matrix[col][row] += value


def convert(input_path: Path, output_path: Path) -> None:
    matrix = [[0.0 for _ in range(SIZE)] for _ in range(SIZE)]
    entries = 0

    for line_no, line in enumerate(input_path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        numbers = parse_numbers(line)
        if not numbers:
            continue

        if len(numbers) >= 5:
            node_i, dof_i, node_j, dof_j = (int(numbers[0]), int(numbers[1]), int(numbers[2]), int(numbers[3]))
            value = numbers[4]
            row = dof_index(node_i, dof_i)
            col = dof_index(node_j, dof_j)
        elif len(numbers) >= 3:
            row = int(numbers[0]) - 1
            col = int(numbers[1]) - 1
            value = numbers[2]
            if not (0 <= row < SIZE and 0 <= col < SIZE):
                raise ValueError(f"matrix index out of 24x24 range at line {line_no}: {line.strip()}")
        else:
            continue

        add_entry(matrix, row, col, value)
        entries += 1

    if entries == 0:
        raise ValueError(f"no matrix entries parsed from {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(matrix)

    print(f"parsed_entries={entries}")
    print(f"wrote={output_path}")


def resolve_input_path(pattern: str) -> Path:
    candidates = sorted(Path(match) for match in glob.glob(pattern))
    if not candidates:
        direct = Path(pattern)
        if direct.exists():
            return direct
        cwd = Path.cwd()
        mtx_files = sorted(cwd.glob("*.mtx"))
        hint = "\n".join(f"  - {path}" for path in mtx_files) if mtx_files else "  no .mtx files in current directory"
        raise FileNotFoundError(
            f"input matrix file not found: {pattern}\n"
            f"Current directory: {cwd}\n"
            f"Try: dir *.mtx\n"
            f"Found candidates:\n{hint}"
        )
    if len(candidates) > 1:
        preferred = [path for path in candidates if "STIF" in path.name.upper()]
        if len(preferred) == 1:
            return preferred[0]
        names = "\n".join(f"  - {path}" for path in candidates)
        raise ValueError(f"multiple files matched {pattern}; pass one explicit file:\n{names}")
    return candidates[0]


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: convert_abaqus_mtx_to_csv.py <input.mtx> <output.csv>", file=sys.stderr)
        return 2

    convert(resolve_input_path(argv[1]), Path(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
