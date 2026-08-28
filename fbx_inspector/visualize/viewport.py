"""向量 / 文字 → Viewport 2.0 DrawOverride 可视化器(路线图占位,仅 Maya)。

目标:对 VEC2/VEC3 数据,在每个面顶点位置用 `MUIDrawManager` 画箭头(方向场、
切线基),或画数值文字标签。完整实现需要一个 `MPxLocatorNode` +
`MPxDrawOverride` 对,并在插件加载时注册结点类型。

v1 先给出接口占位,`apply` 抛 NotImplementedError,把实现留到路线图第 2 步。
届时需在 Maya 2025 内验证 DrawOverride 的注册与绘制。
"""

from __future__ import annotations

from ..core.types import DataKind, DecodedData, VisualizeInfo
from .base import Visualizer


class ViewportVectorVisualizer(Visualizer):
    """占位:用视口箭头绘制向量数据。尚未实现。"""

    accepts = frozenset({DataKind.VEC2, DataKind.VEC3})

    def __init__(self, scale: float = 1.0) -> None:
        self.scale = scale

    def apply(self, mesh, data: DecodedData, ctx) -> VisualizeInfo | None:
        raise NotImplementedError(
            "ViewportVectorVisualizer 属于路线图第 2 步(DrawOverride),尚未实现。"
        )

    def clear(self, mesh, ctx) -> None:
        # 尚无内容可清理。
        return None
