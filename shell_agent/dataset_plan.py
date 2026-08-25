"""数据集规划智能体结构化计划的确定性校验。"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .dataset_verification import DEFAULT_DATASET, load_dataset
from .project_config import ProjectConfig, load_project_config
from .verification import ROOT


ALLOWED_SPLITS = {"train", "validation", "test"}
REQUIRED_FORBIDDEN_CHANGES = {
    "不得使用待评估实现结果作为参考矩阵",
    "不得覆盖已有样本",
    "不得生成没有可信来源记录的CSV",
}


def _existing_sample_ids(dataset_path: Path, project: ProjectConfig) -> set[str]:
    dataset = load_dataset(dataset_path, project)
    identifiers: set[str] = set()
    for split in ALLOWED_SPLITS:
        for relative in dataset[split]:
            payload = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            identifier = payload.get("sample_id")
            if isinstance(identifier, str):
                identifiers.add(identifier)
    return identifiers


def _validate_nodes(nodes: Any, sample_id: str, expected_count: int) -> None:
    if not isinstance(nodes, list) or len(nodes) != expected_count:
        raise ValueError(f"样本 {sample_id} 必须包含{expected_count}个节点")
    coordinates: list[tuple[float, float, float]] = []
    for node in nodes:
        if not isinstance(node, list) or len(node) != 3:
            raise ValueError(f"样本 {sample_id} 节点必须是3维坐标")
        coordinate = tuple(float(value) for value in node)
        if not all(math.isfinite(value) for value in coordinate):
            raise ValueError(f"样本 {sample_id} 节点包含非有限值")
        coordinates.append(coordinate)
    if len(set(coordinates)) != expected_count:
        raise ValueError(f"样本 {sample_id} 节点坐标不能重复")
    if expected_count >= 3:
        first = tuple(coordinates[1][i] - coordinates[0][i] for i in range(3))
        second = tuple(coordinates[2][i] - coordinates[0][i] for i in range(3))
        cross = (
            first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0],
        )
        if math.sqrt(sum(value * value for value in cross)) <= 1.0e-12:
            raise ValueError(f"样本 {sample_id} 几何退化")


def validate_dataset_plan(
    plan_path: Path,
    dataset_path: Path = DEFAULT_DATASET,
) -> dict[str, Any]:
    project = load_project_config()
    plan_path = plan_path if plan_path.is_absolute() else ROOT / plan_path
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    required_strings = {"batch_id", "purpose", "split", "generation_method", "selection_policy"}
    missing = sorted(
        key
        for key in required_strings
        if not isinstance(plan.get(key), str) or not plan[key].strip()
    )
    if plan.get("schema_version") not in {1, 2} or missing:
        raise ValueError(f"数据计划格式不完整：missing={missing}")
    if plan.get("schema_version") == 2:
        if plan.get("project_id") != project.project_id:
            raise ValueError("数据计划 project_id 与当前项目配置不一致")
        if str(plan.get("element_type", "")).casefold() != project.element_type.casefold():
            raise ValueError("数据计划 element_type 与当前项目配置不一致")
    if plan["split"] not in ALLOWED_SPLITS:
        raise ValueError(f"数据计划 split 无效：{plan['split']}")
    if plan["generation_method"] not in set(project.reference_generation_methods):
        raise ValueError(f"数据计划 generation_method 无效：{plan['generation_method']}")
    if plan["split"] == "test" and plan["selection_policy"] != "pre_registered_holdout":
        raise ValueError("测试集计划必须使用 pre_registered_holdout")

    forbidden = plan.get("forbidden_changes")
    if not isinstance(forbidden, list) or not REQUIRED_FORBIDDEN_CHANGES.issubset(set(forbidden)):
        raise ValueError("数据计划缺少必要 forbidden_changes")
    samples = plan.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("数据计划 samples 必须是非空数组")

    existing_ids = _existing_sample_ids(dataset_path, project)
    planned_ids: set[str] = set()
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("数据计划样本必须是对象")
        identifier = sample.get("sample_id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError("数据计划样本缺少 sample_id")
        if identifier in existing_ids or identifier in planned_ids:
            raise ValueError(f"样本 ID 已存在或重复：{identifier}")
        planned_ids.add(identifier)
        if project.node_count is not None:
            _validate_nodes(sample.get("nodes"), identifier, project.node_count)
        if project.adapter_kind == "builtin_s4":
            young = float(sample.get("E", 0.0))
            poisson = float(sample.get("nu", 2.0))
            thickness = float(sample.get("thickness", 0.0))
            if not math.isfinite(young) or young <= 0.0:
                raise ValueError(f"样本 {identifier} 的 E 必须大于0")
            if not math.isfinite(poisson) or not -1.0 < poisson < 0.5:
                raise ValueError(f"样本 {identifier} 的 nu 必须位于 (-1, 0.5)")
            if not math.isfinite(thickness) or thickness <= 0.0:
                raise ValueError(f"样本 {identifier} 的 thickness 必须大于0")
    return plan


def validate_dataset_plan_command(plan_path: Path, dataset_path: Path = DEFAULT_DATASET) -> int:
    try:
        plan = validate_dataset_plan(plan_path, dataset_path)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Dataset plan rejected: {exc}")
        return 4
    print(
        f"Dataset plan accepted: batch={plan['batch_id']}, "
        f"split={plan['split']}, samples={len(plan['samples'])}"
    )
    return 0
