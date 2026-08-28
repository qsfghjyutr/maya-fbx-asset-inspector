"""Ramp 曲线重映射单测(无需 Maya)。"""

from __future__ import annotations

from fbx_inspector.core.remap import Interp, Ramp


def test_linear_is_identity():
    r = Ramp.linear()
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert abs(r(t) - t) < 1e-9


def test_quadratic_matches_square_at_samples():
    r = Ramp.quadratic(samples=8)
    # 采样点上应精确等于 t^2
    assert abs(r(0.5) - 0.25) < 1e-9
    assert abs(r(0.25) - 0.0625) < 1e-9
    assert r(0.0) == 0.0 and r(1.0) == 1.0


def test_output_and_input_clamped_to_unit():
    r = Ramp.from_points([(0.0, 0.2), (1.0, 0.9)])
    assert r(-5.0) == 0.2   # 输入下溢 → 取首点值
    assert r(5.0) == 0.9    # 输入上溢 → 取末点值
    # 值域超界时被夹到 [0,1]
    r2 = Ramp.from_points([(0.0, -1.0), (1.0, 2.0)])
    assert r2(0.0) == 0.0 and r2(1.0) == 1.0


def test_constant_interp_steps():
    r = Ramp.from_points([(0.0, 0.1), (0.5, 0.8), (1.0, 0.8)], interp=Interp.CONSTANT)
    assert r(0.4) == 0.1   # 落在首段 → 取左值
    assert r(0.6) == 0.8


def test_gamma_monotonic():
    r = Ramp.gamma(2.2)
    xs = [i / 20 for i in range(21)]
    ys = [r(x) for x in xs]
    assert all(b >= a - 1e-9 for a, b in zip(ys, ys[1:]))  # 单调不减


def test_requires_two_points():
    try:
        Ramp(points=[(0.0, 0.0)])
    except ValueError:
        return
    raise AssertionError("单控制点应报 ValueError")
