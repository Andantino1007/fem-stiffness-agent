"""配置驱动的训练集、验证集和测试集批量数值验证。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .verification import (
    BUILD_DIR,
    ROOT,
    evaluate_sample,
    prepare_adapter,
    run_adapter_tests,
)
from .project_config import DEFAULT_PROJECT_PATH, ProjectConfig, load_project_config


DEFAULT_DATASET = ROOT / load_project_config().dataset_path
DEFAULT_DATASET_RESULT = BUILD_DIR / "dataset-results.json"
METRIC_LABELS = {
    "frobenius_relative_error": "Frobenius relative error",
    "max_absolute_error": "max absolute error",
    "max_relative_entry_error": "max relative entry error",
    "symmetry_error": "symmetry error",
}


def load_dataset(
    path: Path = DEFAULT_DATASET,
    project: ProjectConfig | None = None,
) -> dict[str, Any]:
    path = path if path.is_absolute() else ROOT / path
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") not in {1, 2}:
        raise ValueError("数据集 schema_version 必须为 1 或 2")
    if payload.get("schema_version") == 2:
        project_id = payload.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("数据集 schema_version 2 必须提供 project_id")
        if project is not None and project_id != project.project_id:
            raise ValueError(
                f"数据集 project_id={project_id} 与当前项目 {project.project_id} 不一致"
            )
    train = payload.get("train")
    validation = payload.get("validation")
    test = payload.get("test")
    if not isinstance(train, list) or not train or not all(isinstance(item, str) for item in train):
        raise ValueError("数据集 train 必须是非空路径数组")
    if not isinstance(validation, list) or not all(isinstance(item, str) for item in validation):
        raise ValueError("数据集 validation 必须是路径数组")
    if not isinstance(test, list) or not all(isinstance(item, str) for item in test):
        raise ValueError("数据集 test 必须是路径数组")
    membership = [*train, *validation, *test]
    duplicates = sorted({item for item in membership if membership.count(item) > 1})
    if duplicates:
        raise ValueError(f"train/validation/test 不能重叠：{duplicates}")
    for relative in membership:
        sample_path = ROOT / relative
        if not sample_path.is_file():
            raise ValueError(f"数据集样本不存在：{relative}")
    return payload


def parse_report(path: Path) -> dict[str, float]:
    text = path.read_text(encoding="utf-8")
    metrics: dict[str, float] = {}
    for key, label in METRIC_LABELS.items():
        match = re.search(rf"{re.escape(label)}:\s*([-+0-9.eE]+)", text)
        if not match:
            raise ValueError(f"样本报告缺少指标：{label}")
        metrics[key] = float(match.group(1))
    return metrics


def sample_id(sample_path: Path) -> str:
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    value = payload.get("sample_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"样本缺少 sample_id：{sample_path.relative_to(ROOT)}")
    return value


def summarize_split(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {"sample_count": 0, "ready": False, "mean_frobenius_relative_error": None, "worst_frobenius_relative_error": None, "worst_sample_id": None}
    errors = [float(item["metrics"]["frobenius_relative_error"]) for item in samples]
    worst_index = max(range(len(samples)), key=lambda index: errors[index])
    return {
        "sample_count": len(samples),
        "ready": True,
        "mean_frobenius_relative_error": sum(errors) / len(errors),
        "worst_frobenius_relative_error": errors[worst_index],
        "worst_sample_id": samples[worst_index]["sample_id"],
    }


def run_dataset_verification(
    dataset_path: Path = DEFAULT_DATASET,
    result_path: Path = DEFAULT_DATASET_RESULT,
    require_test: bool = False,
    project_path: Path = DEFAULT_PROJECT_PATH,
    development_only: bool = False,
) -> int:
    """构建一次适配器并验证三个互斥数据集划分。"""
    try:
        project = load_project_config(project_path)
        dataset = load_dataset(dataset_path, project)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Dataset configuration error: {exc}")
        return 4

    code, runtime = prepare_adapter(project)
    if code != 0:
        return code

    result: dict[str, Any] = {
        "schema_version": 2,
        "project_id": project.project_id,
        "element_type": project.element_type,
        "matrix_dimensions": list(project.matrix_dimensions),
        "dataset": str((dataset_path if dataset_path.is_absolute() else ROOT / dataset_path).relative_to(ROOT)),
        "splits": {},
        "evaluation_scope": "train_validation" if development_only else "all",
    }
    reports_dir = BUILD_DIR / "dataset-reports"
    for split in ("train", "validation", "test"):
        samples: list[dict[str, Any]] = []
        selected = not development_only or split != "test"
        for relative in dataset[split] if selected else []:
            meta_path = ROOT / relative
            identifier = sample_id(meta_path)
            report_path = reports_dir / split / f"{identifier}.md"
            code = evaluate_sample(project, runtime, meta_path, report_path)
            if code != 0:
                return code
            samples.append(
                {
                    "sample_id": identifier,
                    "meta": relative,
                    "report": str(report_path.relative_to(ROOT)),
                    "metrics": parse_report(report_path),
                }
            )
        result["splits"][split] = {
            "samples": samples,
            "summary": summarize_split(samples),
        }

    code = run_adapter_tests(project, runtime)
    if code != 0:
        return code

    result["validation_ready"] = bool(result["splits"]["validation"]["summary"]["ready"])
    result["test_ready"] = bool(
        not development_only and result["splits"]["test"]["summary"]["ready"]
    )
    test_lock_valid = False
    test_lock_message = "测试集为空"
    if result["test_ready"]:
        from .dataset_registry import check_test_lock

        test_lock_valid, test_lock_message = check_test_lock(dataset_path)
    result["test_lock_valid"] = test_lock_valid
    result["test_lock_message"] = test_lock_message
    result["final_evaluation_ready"] = bool(
        not development_only
        and result["validation_ready"]
        and result["test_ready"]
        and test_lock_valid
    )
    result_path = result_path if result_path.is_absolute() else ROOT / result_path
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    train_summary = result["splits"]["train"]["summary"]
    validation_summary = result["splits"]["validation"]["summary"]
    test_summary = result["splits"]["test"]["summary"]
    print()
    print("Dataset verification completed.")
    print(f"Train: {train_summary['sample_count']} sample(s), worst error={train_summary['worst_frobenius_relative_error']}")
    if result["validation_ready"]:
        print(f"Validation: {validation_summary['sample_count']} sample(s), worst error={validation_summary['worst_frobenius_relative_error']}")
    else:
        print("Validation: 0 sample(s), validation_ready=false")
    if result["test_ready"]:
        print(f"Test: {test_summary['sample_count']} sample(s), worst error={test_summary['worst_frobenius_relative_error']}")
        print(f"Test lock: {'valid' if test_lock_valid else 'invalid'} ({test_lock_message})")
    elif development_only:
        print("Test: skipped (development scope never evaluates the locked test set)")
    else:
        print("Test: 0 sample(s), test_ready=false (需要新增独立 Abaqus 基准)")
    print(f"Result: {result_path.relative_to(ROOT)}")
    return 5 if require_test and not result["final_evaluation_ready"] else 0
