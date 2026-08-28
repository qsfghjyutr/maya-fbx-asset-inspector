"""内置校验器(与 Maya 无关)。"""

from __future__ import annotations

import math

from ..core.registry import validator
from ..core.types import DataKind, DecodedData, Issue, Severity
from .base import Validator


def _cap(issues: list[Issue], limit: int) -> list[Issue]:
    """按 max_issues 截断,并在被截断时追加一条汇总说明。"""
    if limit >= 0 and len(issues) > limit:
        kept = issues[:limit]
        kept.append(
            Issue(
                severity=Severity.INFO,
                message=f"……另有 {len(issues) - limit} 条同类问题被省略(超过 max_issues={limit})",
            )
        )
        return kept
    return issues


@validator("range")
class RangeCheck(Validator):
    """检查每个分量是否落在 [min, max] 内。"""

    def __init__(self, minimum: float, maximum: float, severity: Severity = Severity.ERROR) -> None:
        self.minimum = minimum
        self.maximum = maximum
        self.severity = severity

    def validate(self, data: DecodedData) -> list[Issue]:
        issues: list[Issue] = []
        for i, val in enumerate(data.values):
            for comp in val:
                if comp < self.minimum or comp > self.maximum:
                    issues.append(
                        Issue(
                            severity=self.severity,
                            message=f"值 {val} 超出范围 [{self.minimum}, {self.maximum}]",
                            face_id=data.face_ids[i],
                            vertex_id=data.vertex_ids[i],
                            value=val,
                        )
                    )
                    break  # 每个面顶点最多报一次
        return _cap(issues, self.max_issues)


@validator("finite")
class FiniteCheck(Validator):
    """检查是否存在 NaN / Inf。"""

    def validate(self, data: DecodedData) -> list[Issue]:
        issues: list[Issue] = []
        for i, val in enumerate(data.values):
            if any(not math.isfinite(c) for c in val):
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        message=f"存在非有限值(NaN/Inf):{val}",
                        face_id=data.face_ids[i],
                        vertex_id=data.vertex_ids[i],
                        value=val,
                    )
                )
        return _cap(issues, self.max_issues)


@validator("normalized")
class NormalizedCheck(Validator):
    """检查 vec3 是否为单位向量(常用于校验存在顶点色里的法线)。"""

    def __init__(self, tolerance: float = 1e-3) -> None:
        self.tolerance = tolerance

    def validate(self, data: DecodedData) -> list[Issue]:
        if data.kind is not DataKind.VEC3:
            return [
                Issue(
                    severity=Severity.WARNING,
                    message=f"normalized 校验只适用于 VEC3,收到 {data.kind.name},已跳过",
                )
            ]
        issues: list[Issue] = []
        for i, (x, y, z) in enumerate(data.values):
            length = math.sqrt(x * x + y * y + z * z)
            if abs(length - 1.0) > self.tolerance:
                issues.append(
                    Issue(
                        severity=Severity.ERROR,
                        message=f"向量非归一化,模长={length:.4f}",
                        face_id=data.face_ids[i],
                        vertex_id=data.vertex_ids[i],
                        value=(x, y, z),
                    )
                )
        return _cap(issues, self.max_issues)


@validator("constant")
class ConstantCheck(Validator):
    """检查整份数据是否为常量(往往意味着通道没被真正写入)。"""

    def __init__(self, tolerance: float = 1e-6) -> None:
        self.tolerance = tolerance

    def validate(self, data: DecodedData) -> list[Issue]:
        if not data.values:
            return []
        first = data.values[0]
        for val in data.values:
            if any(abs(a - b) > self.tolerance for a, b in zip(val, first)):
                return []  # 存在差异,非常量,正常
        return [
            Issue(
                severity=Severity.WARNING,
                message=f"整个通道为常量 {first};该数据可能未被写入。",
            )
        ]
