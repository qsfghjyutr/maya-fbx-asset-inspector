"""曲线重映射原语 Ramp(与 Maya 无关)。

类似 Houdini VEX 的 chramp:把一个 [0,1] 的输入,经由一条用户定义的曲线,重映射到
[0,1] 的输出,用于在可视化前"塑形"数据(压暗、提亮、增强对比、聚焦某个区间)。

Ramp 由若干控制点 (pos, value) 定义,pos 与 value 均在 [0,1];支持线性 / 平滑
(smoothstep) / 阶梯三种插值。提供 quadratic / gamma / smoothstep 等常用预设。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


class Interp(Enum):
    """控制点之间的插值方式。"""

    LINEAR = "linear"      # 线性
    SMOOTH = "smooth"      # smoothstep 缓入缓出
    CONSTANT = "constant"  # 阶梯(取左侧控制点值)


def _default_points() -> list[tuple[float, float]]:
    return [(0.0, 0.0), (1.0, 1.0)]


@dataclass
class Ramp:
    """一条 [0,1] → [0,1] 的重映射曲线。

    ``points`` 至少两个,按 pos 升序;``__call__(t)`` / ``evaluate(t)`` 求值。
    """

    points: list[tuple[float, float]] = field(default_factory=_default_points)
    interp: Interp = Interp.LINEAR

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("Ramp 至少需要两个控制点")
        self.points = sorted(self.points, key=lambda p: p[0])

    def evaluate(self, t: float) -> float:
        t = clamp01(t)
        pts = self.points
        if t <= pts[0][0]:
            return clamp01(pts[0][1])
        if t >= pts[-1][0]:
            return clamp01(pts[-1][1])
        for (p0, v0), (p1, v1) in zip(pts, pts[1:]):
            if t <= p1:
                span = p1 - p0
                f = 0.0 if span == 0 else (t - p0) / span
                if self.interp is Interp.CONSTANT:
                    return clamp01(v0)
                if self.interp is Interp.SMOOTH:
                    f = f * f * (3.0 - 2.0 * f)
                return clamp01(v0 + (v1 - v0) * f)
        return clamp01(pts[-1][1])

    __call__ = evaluate

    # —— 常用预设 ——
    @classmethod
    def linear(cls) -> "Ramp":
        """恒等映射 y = x。"""
        return cls(_default_points())

    @classmethod
    def quadratic(cls, samples: int = 8) -> "Ramp":
        """二次缓入 y = x^2(采样成折线),即 0-1 区间的二次映射。"""
        pts = [(i / samples, (i / samples) ** 2) for i in range(samples + 1)]
        return cls(pts)

    @classmethod
    def gamma(cls, g: float, samples: int = 16) -> "Ramp":
        """伽马曲线 y = x^g(g<1 提亮,g>1 压暗)。"""
        pts = [(i / samples, (i / samples) ** g) for i in range(samples + 1)]
        return cls(pts)

    @classmethod
    def smoothstep(cls) -> "Ramp":
        """S 形缓入缓出。"""
        return cls([(0.0, 0.0), (1.0, 1.0)], Interp.SMOOTH)

    @classmethod
    def from_points(
        cls, points: list[tuple[float, float]], interp: Interp = Interp.LINEAR
    ) -> "Ramp":
        """从任意控制点构造。"""
        return cls(list(points), interp)
