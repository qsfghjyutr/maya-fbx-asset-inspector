"""可视化器抽象基类与色带工具(与 Maya 无关)。

基类本身不触及 Maya;具体子类(colorset / viewport)才惰性导入 Maya。
色带函数放这里以便脱离 DCC 测试其数值正确性。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.types import DataKind, DecodedData, VisualizeInfo


class Visualizer(ABC):
    """所有可视化器的基类。"""

    #: 该可视化器能处理的数据类型集合。
    accepts: frozenset[DataKind] = frozenset()

    def can_handle(self, kind: DataKind) -> bool:
        return kind in self.accepts

    @abstractmethod
    def apply(self, mesh, data: DecodedData, ctx) -> VisualizeInfo | None:
        """把数据画到 ``mesh`` 上。``mesh`` 为 core.mesh_data.MeshData(仅 Maya)。

        返回可选的 ``VisualizeInfo``(如归一化区间),供报告展示;无可回传信息时返回 None。
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self, mesh, ctx) -> None:
        """撤销本可视化器加到网格上的内容。"""
        raise NotImplementedError


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def ramp_viridis(t: float) -> tuple[float, float, float]:
    """把 t∈[0,1] 映射到一条近似 viridis 的色带(RGB,各∈[0,1])。

    用少量锚点线性插值即可——目的是可读的热力图,而非精确的色彩科学。
    """
    t = clamp01(t)
    stops = (
        (0.0, (0.267, 0.005, 0.329)),
        (0.25, (0.229, 0.322, 0.545)),
        (0.5, (0.128, 0.567, 0.551)),
        (0.75, (0.369, 0.789, 0.383)),
        (1.0, (0.993, 0.906, 0.144)),
    )
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(a + (b - a) * f for a, b in zip(c0, c1))  # type: ignore[return-value]
    return stops[-1][1]


def ramp_grayscale(t: float) -> tuple[float, float, float]:
    v = clamp01(t)
    return (v, v, v)


#: 名称 → 色带函数,供 ColorSetRemapVisualizer 按名选择。
RAMPS = {
    "viridis": ramp_viridis,
    "grayscale": ramp_grayscale,
}
