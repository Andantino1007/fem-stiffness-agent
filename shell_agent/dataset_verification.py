"""训练集/测试集批量 C++ 数值验证。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .verification import (
    BUILD_DIR,
    ROOT,
    compile_verification_binaries,
    run_checked,
)


DEFAULT_DATASET = ROOT / "data" / "datasets" / "shell_stiffness.json"
DEFAULT_DATASET_RESULT = BUILD_DIR / "dataset-results.json"
METRIC_LABELS = {
    "frobenius_relative_error": "Frobenius relative error",
    "max_absolute_error": "max absolute error",
    "max_relative_entry_error": "max relative entry error",
    "symmetry_error": "symmetry error",
}


def load_dataset(path: Path = DEFAULT_DATASET) -> dict[str, Any]:
    path = path if path.is_absolute() else ROOT / path
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("数据集 schema_version 必须为 1")
    train = payload.get("train")
    test = payload.get("test")
    if not isinstance(train, list) or not train or not all(isinstance(item, str) for item in train):
        raise ValueError("数据集 train 必须是非空路径数组")
    if not isinstance(test, list) or not all(isinstance(item, str) for item in test):
        raise ValueError("数据集 test 必须是路径数组")
    duplicates = sorted(set(train) & set(test))
    if duplicates:
        raise ValueError(f"训练集和测试集不能重叠：{duplicates}")
    for relative in [*train, *test]:
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
) -> int:
    """编译一次并验证训练/测试划分中的所有样本。"""
    try:
        dataset = load_dataset(dataset_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Dataset configuration error: {exc}")
        return 4

    code, cli_path, tests_path = compile_verification_binaries()
    if code != 0:
        return code

    result: dict[str, Any] = {
        "schema_version": 1,
        "dataset": str((dataset_path if dataset_path.is_absolute() else ROOT / dataset_path).relative_to(ROOT)),
        "splits": {},
    }
    reports_dir = BUILD_DIR / "dataset-reports"
    for split in ("train", "test"):
        samples: list[dict[str, Any]] = []
        for relative in dataset[split]:
            meta_path = ROOT / relative
            identifier = sample_id(meta_path)
            report_path = reports_dir / split / f"{identifier}.md"
            code = run_checked(
                [
                    str(cli_path),
                    str(meta_path.relative_to(ROOT)),
                    str(report_path.relative_to(ROOT)),
                ]
            )
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

    code = run_checked([str(tests_path)])
    if code != 0:
        return code

    result["test_ready"] = bool(result["splits"]["test"]["summary"]["ready"])
    result_path = result_path if result_path.is_absolute() else ROOT / result_path
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    train_summary = result["splits"]["train"]["summary"]
    test_summary = result["splits"]["test"]["summary"]
    print()
    print("Dataset verification completed.")
    print(f"Train: {train_summary['sample_count']} sample(s), worst error={train_summary['worst_frobenius_relative_error']}")
    if result["test_ready"]:
        print(f"Test: {test_summary['sample_count']} sample(s), worst error={test_summary['worst_frobenius_relative_error']}")
    else:
        print("Test: 0 sample(s), test_ready=false (需要新增独立 Abaqus 基准)")
    print(f"Result: {result_path.relative_to(ROOT)}")
    return 5 if require_test and not result["test_ready"] else 0
