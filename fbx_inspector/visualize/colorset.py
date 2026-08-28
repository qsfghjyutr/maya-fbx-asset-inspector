"""标量 → 显示 color set 可视化器(仅 Maya,惰性导入)。

把标量按色带重映射,写进一个临时 color set,并打开网格的"显示顶点色",
从而复用 Maya 原生视口渲染,无需自定义绘制代码。这是 v1 的主力可视化路径。

⚠️ 本环境无 Maya。写回用的是 `MFnMesh.setFaceVertexColors`,**必须在 Maya 2025
   内验证**面角顺序与该调用签名。
"""

from __future__ import annotations

from ..core.remap import Ramp
from ..core.types import DataKind, DecodedData, VisualizeInfo
from .base import RAMPS, Visualizer, clamp01


def _om():
    import maya.api.OpenMaya as om  # type: ignore[import-not-found]

    return om


def _cmds():
    import maya.cmds as cmds  # type: ignore[import-not-found]

    return cmds


class ColorSetRemapVisualizer(Visualizer):
    """把标量重映射到显示 color set。

    ``normalize=True`` 时按数据自身的 min/max 归一化;否则假定值已在 [0,1]。
    ``curve`` 是可选的 Ramp(chramp 式 0-1→0-1 曲线),在归一化之后、查色带之前施加,
    用于塑形显示而不改动原始数据(校验仍针对原始值)。
    ``set_suffix`` 决定写入哪个 color set(``{prefix}_{suffix}``),不同规则用不同后缀即可
    各写各的 color set、互不覆盖(分通道可视化时尤为关键)。
    """

    accepts = frozenset({DataKind.SCALAR, DataKind.MASK})

    def __init__(
        self,
        ramp: str = "grayscale",
        normalize: bool = True,
        curve: Ramp | None = None,
        set_suffix: str = "remap",
    ) -> None:
        if ramp not in RAMPS:
            raise KeyError(f"未知色带 {ramp!r};可用:{sorted(RAMPS)}")
        self.ramp = RAMPS[ramp]
        self.normalize = normalize
        self.curve = curve
        self.set_suffix = set_suffix

    def _set_name(self, ctx) -> str:
        return f"{ctx.visualize_prefix}_{self.set_suffix}"

    @staticmethod
    def value_range(data: DecodedData) -> tuple[float, float]:
        """当前通道标量的 (min, max)。与 Maya 无关,便于单测与报告复用。"""
        scalars = [v[0] for v in data.values]
        return (min(scalars), max(scalars)) if scalars else (0.0, 1.0)

    def apply(self, mesh, data: DecodedData, ctx) -> VisualizeInfo:
        om = _om()
        cmds = _cmds()
        set_name = self._set_name(ctx)

        scalars = [v[0] for v in data.values]
        lo, hi = self.value_range(data)
        span = (hi - lo) or 1.0

        def to_t(x: float) -> float:
            return clamp01((x - lo) / span) if self.normalize else clamp01(x)

        colors = om.MColorArray()
        faces = om.MIntArray()
        verts = om.MIntArray()
        for i, x in enumerate(scalars):
            t = to_t(x)
            if self.curve is not None:
                t = self.curve(t)  # chramp 式塑形
            r, g, b = self.ramp(t)
            colors.append(om.MColor((r, g, b, 1.0)))
            faces.append(data.face_ids[i])
            verts.append(data.vertex_ids[i])

        name = mesh.name
        existing = cmds.polyColorSet(name, query=True, allColorSets=True) or []
        if set_name not in existing:
            cmds.polyColorSet(name, create=True, colorSet=set_name, representation="RGBA")
        cmds.polyColorSet(name, currentColorSet=True, colorSet=set_name)

        mfn = om.MFnMesh(mesh._dag)  # noqa: SLF001 —— MeshData 内部句柄,可视化器可信任
        mfn.setFaceVertexColors(colors, faces, verts)

        cmds.setAttr(f"{name}.displayColors", 1)

        # 回传归一化区间,让报告显示"颜色是按哪个 min/max 归一化出来的"。
        return VisualizeInfo(normalized=self.normalize, data_min=lo, data_max=hi)

    def clear(self, mesh, ctx) -> None:
        cmds = _cmds()
        set_name = self._set_name(ctx)
        name = mesh.name
        existing = cmds.polyColorSet(name, query=True, allColorSets=True) or []
        if set_name in existing:
            cmds.polyColorSet(name, delete=True, colorSet=set_name)
