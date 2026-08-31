"""数值文字的 Viewport 2.0 可视化器。

文字由 :mod:`viewport_plugin` 的 ``MPxDrawOverride`` 绘制。这里负责将逐面顶点数据
整理为逐几何顶点标签、创建绘制节点并写入数据。Maya 仅在 ``apply`` 时导入。
"""

from __future__ import annotations

import json
from pathlib import Path

from ..core.types import DataKind, DecodedData, VisualizeInfo
from .base import Visualizer

NODE_TYPE = "fbxInspectorValueLabels"
NODE_NAME = "__fbx_inspector_value_labels__"
TRUSTED_PLUGIN = "fbx_inspector_plugin"


def format_value(value: tuple[float, ...], precision: int = 3) -> str:
    """生成紧凑数值文本；向量保留括号，标量只显示数字。"""
    parts = [f"{component:.{precision}f}".rstrip("0").rstrip(".") for component in value]
    parts = ["0" if part in {"", "-0"} else part for part in parts]
    return parts[0] if len(parts) == 1 else f"({', '.join(parts)})"


def build_vertex_labels(data: DecodedData, precision: int = 3) -> dict[int, str]:
    """合并为逐顶点标签；缝两侧的不同值分行显示。"""
    grouped: dict[int, list[str]] = {}
    for vertex_id, value in zip(data.vertex_ids, data.values):
        text = format_value(value, precision)
        values = grouped.setdefault(vertex_id, [])
        if text not in values:
            values.append(text)
    return {vertex_id: "\n".join(values) for vertex_id, values in grouped.items()}


class ViewportTextVisualizer(Visualizer):
    """在对应几何顶点旁绘制解码后的数字。"""

    accepts = frozenset(DataKind)

    def __init__(self, *, font_size: int = 12, precision: int = 3,
                 parent: str | None = None, node_name: str = NODE_NAME) -> None:
        self.font_size = max(1, int(font_size))
        self.precision = max(0, int(precision))
        self.parent = parent
        self.node_name = node_name

    @staticmethod
    def _load_plugin() -> None:
        import maya.cmds as cmds  # type: ignore[import-not-found]

        if cmds.pluginInfo(TRUSTED_PLUGIN, query=True, loaded=True):
            return
        try:
            # 正常安装路径:按名称从 Maya 用户 plug-ins 目录加载可信桥。桥会从仓库导入实际实现。
            cmds.loadPlugin(f"{TRUSTED_PLUGIN}.py", quiet=True)
            return
        except RuntimeError:
            # 仅供未运行 install.py 的源码开发环境使用;Maya 可能对此路径显示安全警告。
            plugin_path = str(Path(__file__).with_name("viewport_plugin.py"))
            cmds.loadPlugin(plugin_path, quiet=True)
        if not cmds.pluginInfo("viewport_plugin", query=True, loaded=True):
            raise RuntimeError("Viewport 2.0 数值标签插件加载失败;请重新运行 install.py")

    def apply(self, mesh, data: DecodedData, ctx) -> VisualizeInfo | None:
        import maya.cmds as cmds  # type: ignore[import-not-found]

        self._load_plugin()
        self.clear(mesh, ctx)
        labels = build_vertex_labels(data, self.precision)
        positions = mesh.vertex_positions()
        payload = [{"p": positions[vid], "text": text}
                   for vid, text in sorted(labels.items()) if 0 <= vid < len(positions)]
        shape = cmds.createNode(NODE_TYPE, name=f"{self.node_name}Shape")
        transform = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
        transform = cmds.rename(transform, self.node_name)
        if self.parent:
            cmds.parent(transform, self.parent, relative=True)
        cmds.setAttr(f"{shape}.labelsJson", json.dumps(payload), type="string")
        cmds.setAttr(f"{shape}.fontSize", self.font_size)
        return None

    def clear(self, mesh, ctx) -> None:
        import maya.cmds as cmds  # type: ignore[import-not-found]

        for node in cmds.ls(self.node_name, long=True) or []:
            if cmds.objExists(node):
                cmds.delete(node)


__all__ = ["ViewportTextVisualizer", "build_vertex_labels", "format_value"]
