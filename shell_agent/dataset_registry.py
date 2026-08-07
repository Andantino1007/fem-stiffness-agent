"""已验证 Abaqus 样本登记与最终测试集哈希锁定。"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .dataset_verification import DEFAULT_DATASET, load_dataset
from .verification import ROOT


DEFAULT_TEST_LOCK = ROOT / "data" / "datasets" / "test-lock.json"
SPLITS = {"train", "validation", "test"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_matrix(path: Path) -> list[list[float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        matrix = [[float(cell) for cell in row] for row in csv.reader(handle) if row]
    if len(matrix) != 24 or any(len(row) != 24 for row in matrix):
        raise ValueError(f"Abaqus 矩阵不是24 x 24：{path}")
    if not all(math.isfinite(value) for row in matrix for value in row):
        raise ValueError(f"Abaqus 矩阵包含非有限值：{path}")
    scale = max(abs(value) for row in matrix for value in row)
    asymmetry = max(
        abs(matrix[row][col] - matrix[col][row])
        for row in range(24)
        for col in range(24)
    )
    if scale <= 0.0 or asymmetry / scale >= 1.0e-10:
        raise ValueError(f"Abaqus 矩阵为空或不对称：{path}")
    return matrix


def validate_sample_artifacts(meta_path: Path) -> dict[str, Any]:
    meta_path = meta_path if meta_path.is_absolute() else ROOT / meta_path
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    identifier = payload.get("sample_id")
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("样本元数据缺少 sample_id")
    source = payload.get("abaqus_matrix_source")
    if not isinstance(source, dict) or source.get("status") != "real_abaqus_export":
        raise ValueError(f"样本 {identifier} 不是可登记的真实 Abaqus 导出")
    matrix_relative = payload.get("abaqus_matrix")
    if not isinstance(matrix_relative, str):
        raise ValueError(f"样本 {identifier} 缺少 abaqus_matrix")
    matrix_path = ROOT / matrix_relative
    _read_matrix(matrix_path)
    return {
        "sample_id": identifier,
        "meta_path": meta_path,
        "matrix_path": matrix_path,
        "meta_relative": str(meta_path.relative_to(ROOT)),
        "matrix_relative": matrix_relative,
    }


def build_test_lock(dataset_path: Path = DEFAULT_DATASET) -> dict[str, Any]:
    dataset = load_dataset(dataset_path)
    entries: list[dict[str, str]] = []
    for relative in dataset["test"]:
        artifact = validate_sample_artifacts(ROOT / relative)
        entries.append(
            {
                "sample_id": artifact["sample_id"],
                "meta": artifact["meta_relative"],
                "meta_sha256": sha256_file(artifact["meta_path"]),
                "abaqus_matrix": artifact["matrix_relative"],
                "matrix_sha256": sha256_file(artifact["matrix_path"]),
            }
        )
    return {"schema_version": 1, "ready": bool(entries), "entries": entries}


def write_test_lock(
    dataset_path: Path = DEFAULT_DATASET,
    lock_path: Path = DEFAULT_TEST_LOCK,
) -> None:
    lock_path = lock_path if lock_path.is_absolute() else ROOT / lock_path
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(
        json.dumps(build_test_lock(dataset_path), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def check_test_lock(
    dataset_path: Path = DEFAULT_DATASET,
    lock_path: Path = DEFAULT_TEST_LOCK,
) -> tuple[bool, str]:
    lock_path = lock_path if lock_path.is_absolute() else ROOT / lock_path
    if not lock_path.is_file():
        return False, "测试集锁文件不存在"
    try:
        expected = json.loads(lock_path.read_text(encoding="utf-8"))
        actual = build_test_lock(dataset_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return False, str(exc)
    if not actual["ready"]:
        return False, "测试集为空"
    if expected != actual:
        return False, "测试集清单或文件哈希已变化"
    return True, "测试集锁定校验通过"


def register_sample(
    meta_path: Path,
    split: str,
    dataset_path: Path = DEFAULT_DATASET,
    lock_path: Path = DEFAULT_TEST_LOCK,
) -> None:
    if split not in SPLITS:
        raise ValueError(f"未知数据集 split：{split}")
    artifact = validate_sample_artifacts(meta_path)
    dataset_path = dataset_path if dataset_path.is_absolute() else ROOT / dataset_path
    dataset = load_dataset(dataset_path)
    all_paths = [item for name in SPLITS for item in dataset[name]]
    all_ids = {
        json.loads((ROOT / relative).read_text(encoding="utf-8")).get("sample_id")
        for relative in all_paths
    }
    if artifact["meta_relative"] in all_paths or artifact["sample_id"] in all_ids:
        raise ValueError(f"样本已经登记：{artifact['sample_id']}")
    dataset[split].append(artifact["meta_relative"])
    dataset_path.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if split == "test":
        write_test_lock(dataset_path, lock_path)


def register_sample_command(meta_path: Path, split: str, dataset_path: Path) -> int:
    try:
        register_sample(meta_path, split, dataset_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Sample registration rejected: {exc}")
        return 4
    print(f"Sample registered: split={split}, meta={meta_path}")
    return 0


def check_test_lock_command(dataset_path: Path, lock_path: Path) -> int:
    passed, message = check_test_lock(dataset_path, lock_path)
    print(message)
    return 0 if passed else 5
