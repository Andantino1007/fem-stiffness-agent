#!/usr/bin/env python3
"""生成通过反力导出 S4 24 x 24 刚度矩阵的 Abaqus 输入文件。

生成的模型包含 24 个静力分析步。每一步对全部 24 个节点自由度施加位移约束：
目标自由度设为 1.0，其余自由度设为 0.0。该步得到的节点反力和力矩构成刚度矩阵的一列。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data" / "abaqus" / "input" / "sample_001_s4_reaction_export.inp"
NODES = [1, 2, 3, 4]
DOFS = [1, 2, 3, 4, 5, 6]


def write_step(lines: list[str], column_index: int, target_node: int, target_dof: int) -> None:
    lines.extend(
        [
            f"*STEP, NAME=K_COL_{column_index:02d}, NLGEOM=NO",
            "*STATIC",
            "*BOUNDARY, OP=NEW",
        ]
    )
    for node in NODES:
        for dof in DOFS:
            value = 1.0 if node == target_node and dof == target_dof else 0.0
            lines.append(f"{node}, {dof}, {dof}, {value:.16g}")
    lines.extend(
        [
            "*OUTPUT, FIELD",
            "*NODE OUTPUT, NSET=ALLNODES",
            "RF, RM",
            "*END STEP",
        ]
    )


def main() -> int:
    lines = [
        "*HEADING",
        "sample_001: S4 stiffness export by 24 unit-displacement reaction steps",
        "*NODE, NSET=ALLNODES",
        "1, 0.0, 0.0, 0.0",
        "2, 1.0, 0.0, 0.0",
        "3, 1.0, 1.0, 0.0",
        "4, 0.0, 1.0, 0.0",
        "*ELEMENT, TYPE=S4, ELSET=EALL",
        "1, 1, 2, 3, 4",
        "*MATERIAL, NAME=STEEL",
        "*ELASTIC",
        "210000000000.0, 0.3",
        "*SHELL SECTION, ELSET=EALL, MATERIAL=STEEL",
        "0.01",
    ]

    column = 1
    for node in NODES:
        for dof in DOFS:
            write_step(lines, column, node, dof)
            column += 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
