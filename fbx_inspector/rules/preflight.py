"""可视化前的网格级检查（与 Maya 无关）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..core.types import Issue, RuleResult, Severity


class PreflightMeshLike(Protocol):
    def uv_set_names(self) -> list[str]: ...


@dataclass(frozen=True)
class UVSetCountCheck:
    """检查 UV 集数量；可用精确值，或最小/最大区间。"""

    expected: int | None = None
    minimum: int | None = None
    maximum: int | None = None
    id: str = "uv_set_count"

    def __post_init__(self) -> None:
        values = (self.expected, self.minimum, self.maximum)
        if all(value is None for value in values):
            raise ValueError("至少需要 expected、minimum 或 maximum 之一")
        if any(value is not None and value < 0 for value in values):
            raise ValueError("UV 集数量要求不能为负数")
        if self.expected is not None and (self.minimum is not None or self.maximum is not None):
            raise ValueError("expected 不能与 minimum/maximum 同时使用")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum 不能大于 maximum")

    def run(self, mesh: PreflightMeshLike, lod: int) -> RuleResult:
        names = list(mesh.uv_set_names())
        count = len(names)
        valid = (
            count == self.expected
            if self.expected is not None
            else (self.minimum is None or count >= self.minimum)
            and (self.maximum is None or count <= self.maximum)
        )
        result = RuleResult(
            rule_id=f"preflight:{self.id}:LOD{lod}",
            label=f"LOD{lod} UV 集数量（实际 {count}：{', '.join(names) or '无'}）",
        )
        if not valid:
            if self.expected is not None:
                requirement = f"应为 {self.expected}"
            elif self.minimum is not None and self.maximum is not None:
                requirement = f"应在 {self.minimum}～{self.maximum} 之间"
            elif self.minimum is not None:
                requirement = f"应不少于 {self.minimum}"
            else:
                requirement = f"应不多于 {self.maximum}"
            result.issues.append(
                Issue(Severity.ERROR, f"UV 集数量{requirement}，实际为 {count}")
            )
        return result


__all__ = ["PreflightMeshLike", "UVSetCountCheck"]
