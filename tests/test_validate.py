"""校验器单测(无需 Maya)。"""

from __future__ import annotations

import math

from fbx_inspector.core.types import DataKind, DecodedData, Severity
from fbx_inspector.validate.builtin import (
    ConstantCheck,
    FiniteCheck,
    NormalizedCheck,
    RangeCheck,
)


def _scalar(values):
    n = len(values)
    return DecodedData(DataKind.SCALAR, [(v,) for v in values], list(range(n)), [0] * n)


def _vec3(values):
    n = len(values)
    return DecodedData(DataKind.VEC3, list(values), list(range(n)), [0] * n)


def test_range_flags_out_of_bounds():
    issues = RangeCheck(0.0, 1.0).validate(_scalar([0.5, 1.5, -0.2]))
    assert len(issues) == 2
    assert all(i.severity is Severity.ERROR for i in issues)
    assert {i.vertex_id for i in issues} == {1, 2}


def test_finite_flags_nan_and_inf():
    issues = FiniteCheck().validate(_scalar([0.1, math.nan, math.inf]))
    assert len(issues) == 2


def test_normalized_passes_unit_vectors_and_flags_others():
    data = _vec3([(1.0, 0.0, 0.0), (0.0, 0.0, 0.0)])
    issues = NormalizedCheck(tolerance=1e-3).validate(data)
    assert len(issues) == 1  # 只有零向量不合格
    assert issues[0].vertex_id == 1


def test_normalized_skips_non_vec3():
    issues = NormalizedCheck().validate(_scalar([0.5]))
    assert len(issues) == 1
    assert issues[0].severity is Severity.WARNING


def test_constant_check_flags_constant_channel():
    assert ConstantCheck().validate(_scalar([0.3, 0.3, 0.3]))
    assert not ConstantCheck().validate(_scalar([0.3, 0.4, 0.3]))


def test_max_issues_cap_appends_summary():
    check = RangeCheck(0.0, 1.0)
    check.max_issues = 3
    issues = check.validate(_scalar([2.0] * 10))
    # 3 条问题 + 1 条汇总
    assert len(issues) == 4
    assert issues[-1].severity is Severity.INFO
