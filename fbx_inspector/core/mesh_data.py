"""网格数据读取(仅 Maya,惰性导入 maya.api.OpenMaya)。

本模块把 Maya 网格上的 color set / UV set 读成与 DCC 无关的 `ChannelData`,
基本单位是**面顶点(face-vertex)**——见 DESIGN.md。

⚠️ 本环境没有 Maya,本文件基于 OpenMaya API 2.0 知识编写,**必须在 Maya 2025 内
   验证**后再信任。最需要核对的是:`MItMeshFaceVertex` 的遍历顺序与
   `getColor` / `getUV` 的行为。
"""

from __future__ import annotations

from .channel import Channel, ChannelData, SourceType


def _om():
    """惰性导入 OpenMaya,使本模块在无 Maya 环境也能被 import。"""
    import maya.api.OpenMaya as om  # type: ignore[import-not-found]

    return om


def get_mesh_dag(name: str):
    """按结点名解析出网格的 DAG 路径(MDagPath)。"""
    om = _om()
    sel = om.MSelectionList()
    sel.add(name)
    dag = sel.getDagPath(0)
    dag.extendToShape()  # 传入 transform 时下探到 shape
    return dag


class MeshData:
    """对单个网格的读取封装。构造需在 Maya 内进行。"""

    def __init__(self, mesh_name: str) -> None:
        self._name = mesh_name
        self._dag = get_mesh_dag(mesh_name)

    @property
    def name(self) -> str:
        return self._name

    def color_set_names(self) -> list[str]:
        om = _om()
        return list(om.MFnMesh(self._dag).getColorSetNames())

    def uv_set_names(self) -> list[str]:
        om = _om()
        return list(om.MFnMesh(self._dag).getUVSetNames())

    def available_channels(self) -> list[Channel]:
        """把网格上所有 color set 与 UV set 枚举成 Channel。"""
        chans = [Channel(SourceType.COLOR_SET, n) for n in self.color_set_names()]
        chans += [Channel(SourceType.UV_SET, n) for n in self.uv_set_names()]
        return chans

    def vertex_positions(self) -> list[tuple[float, float, float]]:
        """返回网格对象空间的逐顶点位置，供视口标注等只读可视化使用。"""
        om = _om()
        points = om.MFnMesh(self._dag).getPoints(om.MSpace.kObject)
        return [(float(p.x), float(p.y), float(p.z)) for p in points]

    def read_channel(self, channel: Channel) -> ChannelData:
        """按面顶点顺序读取一个通道的原始分量。

        用 MItMeshFaceVertex 逐面角遍历,保证与硬边 / UV 缝一致的逐面顶点语义。
        注意:这是"正确优先"的实现;大网格上的向量化加速属于后续优化。
        """
        om = _om()
        it = om.MItMeshFaceVertex(self._dag)
        data = ChannelData(channel=channel)

        if channel.source is SourceType.COLOR_SET:
            data.components = {c: [] for c in ("R", "G", "B", "A")}
            while not it.isDone():
                # 某些面角可能未被指派颜色;缺失时以 (0,0,0,1) 兜底。
                try:
                    c = it.getColor(channel.name)
                    rgba = (c.r, c.g, c.b, c.a)
                except RuntimeError:
                    rgba = (0.0, 0.0, 0.0, 1.0)
                for key, val in zip(("R", "G", "B", "A"), rgba):
                    data.components[key].append(val)
                data.vertex_ids.append(it.vertexId())
                data.face_ids.append(it.faceId())
                it.next()
        elif channel.source is SourceType.UV_SET:
            data.components = {"U": [], "V": []}
            while not it.isDone():
                if it.hasUVs(channel.name):
                    u, v = it.getUV(channel.name)
                else:
                    u = v = 0.0
                data.components["U"].append(u)
                data.components["V"].append(v)
                data.vertex_ids.append(it.vertexId())
                data.face_ids.append(it.faceId())
                it.next()
        else:  # 防御:未来新增来源类型时提醒补分支
            raise ValueError(f"未知的通道来源类型:{channel.source}")

        return data
