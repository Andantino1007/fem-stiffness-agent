# 使用 Abaqus Python 运行：
#   abaqus python scripts\abaqus\extract_reaction_stiffness_from_odb.py sample_001_s4_reaction_export.odb data\abaqus\matrix\sample_001_abaqus_s4.csv

from __future__ import annotations

import csv
import sys
from pathlib import Path

from odbAccess import openOdb  # type: ignore


NODE_ORDER = [1, 2, 3, 4]
DOF_PER_NODE = 6
SIZE = len(NODE_ORDER) * DOF_PER_NODE


def collect_nodal_vector(frame):
    rf = frame.fieldOutputs.get("RF")
    rm = frame.fieldOutputs.get("RM")
    if rf is None:
        raise RuntimeError("ODB frame has no RF field output")

    rf_by_node = {value.nodeLabel: value.data for value in rf.values}
    rm_by_node = {value.nodeLabel: value.data for value in rm.values} if rm is not None else {}

    vector = []
    for node in NODE_ORDER:
        force = rf_by_node.get(node, (0.0, 0.0, 0.0))
        moment = rm_by_node.get(node, (0.0, 0.0, 0.0))
        vector.extend([force[0], force[1], force[2], moment[0], moment[1], moment[2]])
    return vector


def extract(odb_path: Path, csv_path: Path, negate: bool = False) -> None:
    odb = openOdb(str(odb_path), readOnly=True)
    try:
        matrix = [[0.0 for _ in range(SIZE)] for _ in range(SIZE)]
        step_names = sorted(name for name in odb.steps.keys() if name.startswith("K_COL_"))
        if len(step_names) != SIZE:
            raise RuntimeError("expected 24 K_COL_* steps, found %d" % len(step_names))

        for col, step_name in enumerate(step_names):
            frame = odb.steps[step_name].frames[-1]
            vector = collect_nodal_vector(frame)
            if len(vector) != SIZE:
                raise RuntimeError("expected 24 reaction values in %s, found %d" % (step_name, len(vector)))
            for row, value in enumerate(vector):
                matrix[row][col] = -value if negate else value
    finally:
        odb.close()

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(matrix)
    print("wrote=%s" % csv_path)


def main(argv):
    if len(argv) not in (3, 4):
        print("Usage: abaqus python extract_reaction_stiffness_from_odb.py <input.odb> <output.csv> [--negate]", file=sys.stderr)
        return 2
    extract(Path(argv[1]), Path(argv[2]), negate=(len(argv) == 4 and argv[3] == "--negate"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
