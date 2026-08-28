"""嵌入到 Qt 里的隔离 Maya 视口(仅 Maya,惰性导入)。

`IsolatedMeshView` 负责:复制目标网格 → 偏移进专属组 → 建专属相机与 modelPanel →
把 modelPanel 的 QWidget 取出交给窗口内嵌 → 用 per-panel isolateSelect 让该面板**只**显示
副本。着色写在副本的显示 color set 上,因此**主视口/场景观感始终不变**;关闭时清理副本、
相机、面板。

⚠️ 本环境无 Maya GUI。`cmds.modelPanel` 需要 GUI,无法用 mayapy standalone 无头验证,
   **必须在 Maya 2025 GUI 内手测**。副本着色链路(复制 + 写 color set)可无头验证。
"""

from __future__ import annotations

GROUP_NAME = "__fbx_inspector_grp__"
CONTENT_NAME = "__fbx_inspector_content__"
DUP_NAME = "__fbx_inspector_dup__"
CAM_NAME = "__fbx_inspector_cam__"
VIEW_SET_SUFFIX = "view"
_OFFSET = 100000.0  # 把副本偏到远处,主相机常态下看不见
# 相机的确定朝向:对齐 Maya 默认 persp 的 3/4 视角。固定朝向(而非新相机默认 -Z + viewFit)
# 可避免取景方向不确定造成的"Z 反了"错觉,配合大坐标轴 gizmo 一起消除方位歧义。
_CAM_ROT = (-27.938, 45.0, 0.0)


def _cmds():
    import maya.cmds as cmds  # type: ignore[import-not-found]

    return cmds


def _omui():
    import maya.OpenMayaUI as omui  # type: ignore[import-not-found]

    return omui


def _wrap_instance():
    # Maya 2025 = PySide6 / shiboken6;兼容旧版回退到 shiboken2。
    try:
        from shiboken6 import wrapInstance  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - 旧版 Maya
        from shiboken2 import wrapInstance  # type: ignore[import-not-found]
    return wrapInstance


def _qwidget_cls():
    try:
        from PySide6.QtWidgets import QWidget  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - 旧版 Maya
        from PySide2.QtWidgets import QWidget  # type: ignore[import-not-found]
    return QWidget


class IsolatedMeshView:
    """管理一份隔离显示的网格副本及其内嵌视口。"""

    def __init__(self, source_mesh: str) -> None:
        cmds = _cmds()

        self.source = source_mesh
        self._alive = False
        self._coord_id = "maya"  # 当前坐标约定;默认 Maya(恒等,不变换)
        self._mirrored = False   # content 变换当前是否已翻手性(与法线反转配对)

        # 1) 复制源网格。dup 放进 content(承载坐标约定变换),content 再放进 group
        #    (只负责把整体平移到远处隐藏)。两层职责分离:变换归 content,隐藏归 group。
        dup = cmds.duplicate(source_mesh, name=DUP_NAME, returnRootsOnly=True)[0]
        self.dup = dup
        self.content = cmds.group(dup, name=CONTENT_NAME, world=True)
        self.group = cmds.group(self.content, name=GROUP_NAME, world=True)
        cmds.setAttr(f"{self.group}.translateX", _OFFSET)

        # 2) 专属相机 —— 给一个确定的 3/4 朝向,不再依赖"默认朝向 + viewFit"的不确定取景
        self.camera = cmds.camera(name=CAM_NAME)[0]
        cmds.setAttr(f"{self.camera}.rotate", *_CAM_ROT)

        # 3) modelPanel,并把它的 QWidget 取出供窗口内嵌
        self.panel = cmds.modelPanel(menuBarVisible=False)
        cmds.modelPanel(self.panel, edit=True, camera=self.camera)
        editor = cmds.modelPanel(self.panel, query=True, modelEditor=True)
        # 视口显示精简:关网格线、只显示多边形
        cmds.modelEditor(editor, edit=True, grid=False, displayAppearance="smoothShaded")

        ptr = _omui().MQtUtil.findControl(self.panel)
        self.widget = _wrap_instance()(int(ptr), _qwidget_cls())

        # 4) per-panel 隔离:本面板只显示 content(含副本),不影响主视口
        cmds.isolateSelect(self.panel, state=True)
        cmds.isolateSelect(self.panel, addDagObject=self.content)

        # 5) 相机框住副本(临时改选集后还原,避免干扰用户当前选择)
        self._fit_camera()

        self._alive = True

    def _fit_camera(self) -> None:
        """让专属相机框住副本,期间不改动用户当前选择。"""
        cmds = _cmds()
        prev = cmds.ls(selection=True, long=True)
        try:
            cmds.select(self.dup, replace=True)
            cmds.viewFit(self.camera, animate=False)
        finally:
            if prev:
                cmds.select(prev, replace=True)
            else:
                cmds.select(clear=True)

    def camera_view_rotation(self):
        """相机的世界→相机旋转(3x3),供右上角方向指示器把世界轴投影到屏幕。

        Maya 的世界矩阵是行主序、行向量约定(p_world = p_local · M),其前三行的前三列即相机
        局部 X/Y/Z 轴在世界里的方向;用它把世界向量点乘到相机局部系,即所需的投影矩阵。
        惰性:方向指示器每帧调它取当前镜头姿态,故 tumble 时会实时更新。
        """
        from ..core.coord_convention import view_rotation_from_matrix

        cmds = _cmds()
        m16 = cmds.xform(self.camera, query=True, worldSpace=True, matrix=True)
        return view_rotation_from_matrix(m16)

    def current_convention(self):
        """当前坐标约定对象(供指示器按约定摆放/标注轴)。"""
        from ..core.coord_convention import CONVENTIONS

        return CONVENTIONS[self._coord_id]

    def set_coord_convention(self, convention_id: str) -> None:
        """把 content 摆成目标坐标约定的姿态(如 UE 的 Z-up 左手),并补偿镜像。

        只作用于窗口里的副本 content,**完全不触碰原始场景网格**;也不影响 ``show_channel``
        按 face-vertex 索引写颜色的逻辑(世界变换与索引式顶点色读写互不相关)。
        """
        cmds = _cmds()
        from ..core.coord_convention import CONVENTIONS, to_maya_matrix44

        conv = CONVENTIONS[convention_id]
        cmds.xform(self.content, matrix=to_maya_matrix44(conv.matrix), objectSpace=True)

        # 换手性(镜像)会让面背朝外,反转一次副本法线/绕序补偿。
        if conv.is_mirror != self._mirrored:
            cmds.polyNormal(self.dup, normalMode=0, userNormalMode=0, ch=False)
            self._mirrored = conv.is_mirror

        self._coord_id = convention_id
        self._fit_camera()  # 姿态变了,重新取景


    def show_channel(self, rule, source_view) -> object:
        """按规则读取源网格通道 → 解码 → 给副本着色 → 刷新;返回 RuleResult(含校验)。

        ``rule`` 来自 ``ui.channels.scalar_rule_for``;``source_view`` 是源网格的
        ``core.mesh_data.MeshData``(从它读原始数据,着色写到副本上)。
        """
        cmds = _cmds()
        from ..core.context import InspectionContext
        from ..core.mesh_data import MeshData
        from ..core.types import RuleResult

        channels = {
            role: source_view.read_channel(ch) for role, ch in rule.channel_roles.items()
        }
        decoded = rule.decoder.decode(channels)

        dup_view = MeshData(self.dup)
        ctx = InspectionContext(mesh_name=self.dup)
        info = rule.visualizer.apply(dup_view, decoded, ctx)  # 写副本的显示 color set
        cmds.refresh()

        result = RuleResult(
            rule_id=rule.id, label=decoded.label, visualized=True, viz_info=info
        )
        for v in rule.validators:
            result.issues.extend(v.validate(decoded))
        return result

    def cleanup(self) -> None:
        """删除面板、相机与副本组。可重复调用。"""
        if not self._alive:
            return
        cmds = _cmds()
        for action in (
            lambda: cmds.deleteUI(self.panel, panel=True),
            lambda: cmds.delete(self.group),
            lambda: cmds.delete(self.camera),
        ):
            try:
                action()
            except Exception:  # noqa: BLE001 —— 清理阶段尽力而为,不因单点失败中断
                pass
        self._alive = False
