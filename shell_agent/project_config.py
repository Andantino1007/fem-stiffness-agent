"""通用单元工作流的项目配置。"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_PATH = ROOT / "workflow" / "project.json"
SUPPORTED_ADAPTERS = {"builtin_s4", "command"}


def _relative_path(value: Any, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"项目配置 {field} 必须是非空路径")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"项目配置 {field} 必须是工作区内相对路径")
    return path


def _string_list(value: Any, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(f"项目配置 {field} 必须是字符串数组")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"项目配置 {field} 包含空值或非字符串")
    if len(value) != len(set(value)):
        raise ValueError(f"项目配置 {field} 不能包含重复值")
    return tuple(value)


def _command(value: Any, field: str, *, required: bool) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    return _string_list(value, field)


@dataclass(frozen=True)
class ProjectConfig:
    path: Path
    project_id: str
    element_type: str
    matrix_dimensions: tuple[int, int]
    node_count: int | None
    dof_labels_per_node: tuple[str, ...]
    diagnostic_groups: dict[str, tuple[str | int, ...]]
    dataset_path: Path
    primary_sample_path: Path
    reference_generation_methods: tuple[str, ...]
    adapter_kind: str
    build_command: tuple[str, ...]
    evaluate_command: tuple[str, ...]
    test_command: tuple[str, ...]
    allowed_patch_paths: tuple[str, ...]
    test_paths: tuple[str, ...]
    experiment_classes: tuple[str, ...]
    acceptance: dict[str, float]
    raw: dict[str, Any]

    @property
    def matrix_size(self) -> int:
        return self.matrix_dimensions[0]

    @property
    def block_names(self) -> tuple[str, ...]:
        return tuple(self.diagnostic_groups)

    @property
    def block_metric_keys(self) -> set[str]:
        return {
            f"{row_name}__{col_name}"
            for row_name in self.block_names
            for col_name in self.block_names
        }

    def absolute(self, relative: Path | str) -> Path:
        return ROOT / relative

    def dof_label(self, index: int) -> str:
        if self.node_count and self.dof_labels_per_node:
            width = len(self.dof_labels_per_node)
            return f"n{index // width + 1}.{self.dof_labels_per_node[index % width]}"
        return f"dof_{index + 1}"

    def diagnostic_index_groups(self) -> dict[str, list[int]]:
        groups: dict[str, list[int]] = {}
        labels = self.dof_labels_per_node
        for name, members in self.diagnostic_groups.items():
            if members and all(isinstance(item, int) for item in members):
                indices = [int(item) for item in members]
            elif self.node_count and labels and all(isinstance(item, str) for item in members):
                offsets = [labels.index(str(item)) for item in members]
                indices = [
                    node * len(labels) + offset
                    for node in range(self.node_count)
                    for offset in offsets
                ]
            else:
                raise ValueError(f"诊断分组 {name} 无法映射到矩阵自由度")
            if not indices or min(indices) < 0 or max(indices) >= self.matrix_size:
                raise ValueError(f"诊断分组 {name} 包含越界自由度")
            groups[name] = indices
        return groups

    def prompt_payload(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "element_type": self.element_type,
            "matrix_dimensions": list(self.matrix_dimensions),
            "adapter_kind": self.adapter_kind,
            "dataset": str(self.dataset_path),
            "primary_sample": str(self.primary_sample_path),
            "reference_generation_methods": list(self.reference_generation_methods),
            "diagnostic_groups": {
                key: list(value) for key, value in self.diagnostic_groups.items()
            },
            "allowed_patch_paths": list(self.allowed_patch_paths),
            "experiment_classes": list(self.experiment_classes),
            "target_error": self.acceptance["target_error"],
        }


def load_project_config(path: Path = DEFAULT_PROJECT_PATH) -> ProjectConfig:
    path = path if path.is_absolute() else ROOT / path
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("项目配置 schema_version 必须为 1")

    project_id = payload.get("project_id")
    element_type = payload.get("element_type")
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("项目配置缺少 project_id")
    if not isinstance(element_type, str) or not element_type.strip():
        raise ValueError("项目配置缺少 element_type")

    dimensions = payload.get("matrix_dimensions")
    if (
        not isinstance(dimensions, list)
        or len(dimensions) != 2
        or not all(isinstance(value, int) and value > 0 for value in dimensions)
        or dimensions[0] != dimensions[1]
    ):
        raise ValueError("matrix_dimensions 必须是两个相等的正整数")
    matrix_dimensions = (dimensions[0], dimensions[1])

    node_count_value = payload.get("node_count")
    node_count = None
    if node_count_value is not None:
        if not isinstance(node_count_value, int) or node_count_value <= 0:
            raise ValueError("node_count 必须是正整数")
        node_count = node_count_value
    labels = _string_list(
        payload.get("dof_labels_per_node", []),
        "dof_labels_per_node",
        allow_empty=node_count is None,
    )
    if node_count is not None and node_count * len(labels) != matrix_dimensions[0]:
        raise ValueError("node_count * dof_labels_per_node 数量必须等于矩阵尺寸")

    raw_groups = payload.get("diagnostic_groups")
    if not isinstance(raw_groups, dict) or not raw_groups:
        raw_groups = {"all": list(range(matrix_dimensions[0]))}
    groups: dict[str, tuple[str | int, ...]] = {}
    for name, members in raw_groups.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(members, list) or not members:
            raise ValueError("diagnostic_groups 必须是非空名称到非空数组的映射")
        if not all(isinstance(item, (str, int)) and not isinstance(item, bool) for item in members):
            raise ValueError(f"诊断分组 {name} 只能包含自由度名称或整数索引")
        if labels and any(isinstance(item, str) and item not in labels for item in members):
            raise ValueError(f"诊断分组 {name} 引用了未知自由度名称")
        groups[name] = tuple(members)

    adapter = payload.get("adapter")
    if not isinstance(adapter, dict) or adapter.get("kind") not in SUPPORTED_ADAPTERS:
        raise ValueError(f"adapter.kind 必须是 {sorted(SUPPORTED_ADAPTERS)} 之一")
    adapter_kind = str(adapter["kind"])
    if adapter_kind == "builtin_s4" and (
        matrix_dimensions != (24, 24) or node_count != 4 or len(labels) != 6
    ):
        raise ValueError(
            "builtin_s4 仅实现4节点、每节点6自由度的24 x 24内核；"
            "其他单元请使用 command 适配器"
        )
    build_command = _command(adapter.get("build_command"), "adapter.build_command", required=False)
    evaluate_command = _command(adapter.get("evaluate_command"), "adapter.evaluate_command", required=adapter_kind == "command")
    test_command = _command(adapter.get("test_command"), "adapter.test_command", required=False)

    agent = payload.get("agent")
    if not isinstance(agent, dict):
        raise ValueError("项目配置缺少 agent")
    allowed_patch_paths = _string_list(agent.get("allowed_patch_paths"), "agent.allowed_patch_paths")
    test_paths = _string_list(agent.get("test_paths", []), "agent.test_paths", allow_empty=True)
    experiment_classes = _string_list(agent.get("experiment_classes"), "agent.experiment_classes")
    for relative in (*allowed_patch_paths, *test_paths):
        _relative_path(relative, "agent 路径")

    defaults = {
        "target_error": 0.01,
        "min_frobenius_absolute_drop": 1.0e-6,
        "min_frobenius_relative_drop": 1.0e-4,
        "max_symmetry_error": 1.0e-12,
        "max_absolute_error_regression": 0.01,
        "max_non_target_block_regression": 0.05,
        "max_validation_error_regression": 0.0,
    }
    raw_acceptance = payload.get("acceptance", {})
    if not isinstance(raw_acceptance, dict):
        raise ValueError("acceptance 必须是对象")
    acceptance: dict[str, float] = {}
    for key, default in defaults.items():
        value = raw_acceptance.get(key, default)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError(f"acceptance.{key} 必须是有限数值")
        acceptance[key] = float(value)
    if not 0.0 < acceptance["target_error"] < 1.0:
        raise ValueError("acceptance.target_error 必须位于 (0, 1)")
    if any(acceptance[key] < 0.0 for key in defaults if key != "target_error"):
        raise ValueError("acceptance 门槛不能为负数")

    config = ProjectConfig(
        path=path,
        project_id=project_id,
        element_type=element_type,
        matrix_dimensions=matrix_dimensions,
        node_count=node_count,
        dof_labels_per_node=labels,
        diagnostic_groups=groups,
        dataset_path=_relative_path(payload.get("dataset"), "dataset"),
        primary_sample_path=_relative_path(payload.get("primary_sample"), "primary_sample"),
        reference_generation_methods=_string_list(
            payload.get("reference_generation_methods", ["external_solver"]),
            "reference_generation_methods",
        ),
        adapter_kind=adapter_kind,
        build_command=build_command,
        evaluate_command=evaluate_command,
        test_command=test_command,
        allowed_patch_paths=allowed_patch_paths,
        test_paths=test_paths,
        experiment_classes=experiment_classes,
        acceptance=acceptance,
        raw=payload,
    )
    config.diagnostic_index_groups()
    return config


def project_config_command(path: Path = DEFAULT_PROJECT_PATH) -> int:
    try:
        config = load_project_config(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Project configuration rejected: {exc}")
        return 4
    print(f"Project: {config.project_id}")
    print(f"Element type: {config.element_type}")
    print(f"Matrix dimensions: {config.matrix_size} x {config.matrix_size}")
    print(f"Adapter: {config.adapter_kind}")
    print(f"Dataset: {config.dataset_path}")
    print("Project configuration passed.")
    return 0
