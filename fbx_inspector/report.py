"""报告聚合与输出(与 Maya 无关)。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .core.types import RuleResult, Severity


@dataclass
class Report:
    """一次检查运行的汇总:针对某个资产的一组规则结果。"""

    asset_name: str
    results: list[RuleResult] = field(default_factory=list)

    @property
    def total_errors(self) -> int:
        return sum(r.error_count for r in self.results)

    @property
    def total_warnings(self) -> int:
        return sum(r.warning_count for r in self.results)

    @property
    def passed(self) -> bool:
        return self.total_errors == 0

    def to_text(self) -> str:
        """人类可读的文本报告。"""
        lines = [
            f"资产:{self.asset_name}",
            f"结果:{'通过' if self.passed else '未通过'} "
            f"（错误 {self.total_errors}，警告 {self.total_warnings}）",
            "",
        ]
        for r in self.results:
            head = f"[规则 {r.rule_id}]"
            if r.label:
                head += f" {r.label}"
            head += f" —— 错误 {r.error_count}，警告 {r.warning_count}"
            if r.visualized:
                head += "，已可视化"
            lines.append(head)
            info = r.viz_info
            if info is not None and info.data_min is not None:
                prefix = "归一化区间" if info.normalized else "数据区间（未归一化）"
                lines.append(
                    f"    {prefix}：min={info.data_min:.6g}，max={info.data_max:.6g}"
                )
            for issue in r.issues:
                loc = ""
                if issue.face_id >= 0:
                    loc = f"（face {issue.face_id}, vtx {issue.vertex_id}）"
                lines.append(f"    - {issue.severity.value.upper()}: {issue.message} {loc}".rstrip())
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """结构化字典,便于序列化 / CI 消费。"""
        return {
            "asset": self.asset_name,
            "passed": self.passed,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "results": [
                {
                    "rule_id": r.rule_id,
                    "label": r.label,
                    "visualized": r.visualized,
                    "normalization": (
                        {
                            "normalized": r.viz_info.normalized,
                            "data_min": r.viz_info.data_min,
                            "data_max": r.viz_info.data_max,
                        }
                        if r.viz_info is not None
                        else None
                    ),
                    "issues": [
                        {
                            "severity": i.severity.value,
                            "message": i.message,
                            "face_id": i.face_id,
                            "vertex_id": i.vertex_id,
                            "value": list(i.value) if i.value is not None else None,
                        }
                        for i in r.issues
                    ],
                }
                for r in self.results
            ],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def build_report(asset_name: str, results: list[RuleResult]) -> Report:
    return Report(asset_name=asset_name, results=results)


__all__ = ["Report", "build_report", "Severity"]
