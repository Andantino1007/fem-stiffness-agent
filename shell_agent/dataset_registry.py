"""已验证 Abaqus 样本登记与最终测试集哈希锁定。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .dataset_verification import DEFAULT_DATASET, load_dataset
from .matrix_validation import validate_reference_matrix
from .project_config import ProjectConfig, load_project_config
from .verification import ROOT


DEFAULT_TEST_LOCK = ROOT / "data" / "datasets" / "test-lock.json"
SPLITS = {"train", "validation", "test"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_sample_artifacts(
    meta_path: Path,
    project: ProjectConfig | None = None,
) -> dict[str, Any]:
    project = project or load_project_config()
    meta_path = meta_path if meta_path.is_absolute() else ROOT / meta_path
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    identifier = payload.get("sample_id")
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("样本元数据缺少 sample_id")
    sample_element = payload.get("element_type")
    if not isinstance(sample_element, str) or not sample_element.strip():
        raise ValueError(f"样本 {identifier} 缺少 element_type")
    if sample_element.casefold() != project.element_type.casefold():
        raise ValueError(
            f"样本 {identifier} 的 element_type={sample_element} 与项目配置不一致"
        )
    source = payload.get("reference_matrix_source", payload.get("abaqus_matrix_source"))
    allowed_statuses = {"real_abaqus_export", "verified_external_reference"}
    if not isinstance(source, dict) or source.get("status") not in allowed_statuses:
        raise ValueError(f"样本 {identifier} 缺少可信参考矩阵来源")
    matrix_relative = payload.get("reference_matrix", payload.get("abaqus_matrix"))
    if not isinstance(matrix_relative, str):
        raise ValueError(f"样本 {identifier} 缺少 reference_matrix")
    matrix_path = ROOT / matrix_relative
    validate_reference_matrix(matrix_path, project.matrix_size)
    return {
        "sample_id": identifier,
        "meta_path": meta_path,
        "matrix_path": matrix_path,
        "meta_relative": meta_path.relative_to(ROOT).as_posix(),
        "matrix_relative": matrix_relative,
    }


def build_test_lock(dataset_path: Path = DEFAULT_DATASET) -> dict[str, Any]:
    project = load_project_config()
    dataset = load_dataset(dataset_path, project)
    entries: list[dict[str, str]] = []
    for relative in dataset["test"]:
        artifact = validate_sample_artifacts(ROOT / relative, project)
        entries.append(
            {
                "sample_id": artifact["sample_id"],
                "meta": artifact["meta_relative"],
                "meta_sha256": sha256_file(artifact["meta_path"]),
                "reference_matrix": artifact["matrix_relative"],
                "matrix_sha256": sha256_file(artifact["matrix_path"]),
            }
        )
    return {
        "schema_version": 2,
        "project_id": project.project_id,
        "matrix_dimensions": list(project.matrix_dimensions),
        "ready": bool(entries),
        "entries": entries,
    }


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
    project = load_project_config()
    artifact = validate_sample_artifacts(meta_path, project)
    dataset_path = dataset_path if dataset_path.is_absolute() else ROOT / dataset_path
    dataset = load_dataset(dataset_path, project)
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
