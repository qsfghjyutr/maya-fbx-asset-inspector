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
AXES_NAME = "__fbx_inspector_origin_axes__"
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
        self._convert_uv = True  # 是否随约定同步转换 UV 空间(UE 的 V→1-V);默认开
        self._hidden_history: list[list[str]] = []  # 仅记录检查器副本,不污染 Maya 全局隐藏历史

        # 1) 复制源网格。content 是副本与原点轴的稳定预览容器;group 只负责远距隐藏。
        dup = cmds.duplicate(source_mesh, name=DUP_NAME, returnRootsOnly=True)[0]
        self.dup = dup
        self.content = cmds.group(dup, name=CONTENT_NAME, world=True)
        self.group = cmds.group(self.content, name=GROUP_NAME, world=True)
        cmds.setAttr(f"{self.group}.translateX", _OFFSET)
        self._origin_axes: list[str] = []
        self._axis_length = self._origin_axis_length(source_mesh)
        self._create_origin_axes()

        # 2) 专属相机 —— 给一个确定的 3/4 朝向,不再依赖"默认朝向 + viewFit"的不确定取景
        self.camera = cmds.camera(name=CAM_NAME)[0]
        cmds.setAttr(f"{self.camera}.rotate", *_CAM_ROT)

        # 3) modelPanel,并把它的 QWidget 取出供窗口内嵌
        self.panel = cmds.modelPanel(menuBarVisible=False)
        cmds.modelPanel(self.panel, edit=True, camera=self.camera)
        editor = cmds.modelPanel(self.panel, query=True, modelEditor=True)
        # 视口显示精简:关网格线、只显示多边形
        cmds.modelEditor(
            editor, edit=True, grid=False, locators=True, displayAppearance="smoothShaded"
        )

        ptr = _omui().MQtUtil.findControl(self.panel)
        self.widget = _wrap_instance()(int(ptr), _qwidget_cls())

        # 4) per-panel 隔离:本面板只显示 content(含副本),不影响主视口
        cmds.isolateSelect(self.panel, state=True)
        cmds.isolateSelect(self.panel, addDagObject=self.content)

        # 5) 相机框住副本(临时改选集后还原,避免干扰用户当前选择)
        self._fit_camera()

        self._alive = True

    def _origin_axis_length(self, mesh: str) -> float:
        """计算从原点向正负方向贯穿资产的对称坐标轴长度。"""
        bb = _cmds().exactWorldBoundingBox(mesh)
        extent = max(abs(value) for value in bb)
        span = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])
        return max(1.0, extent + span * 0.1)

    def _create_origin_axes(self) -> None:
        """创建贯穿预览原点的 RGB 细线坐标轴。"""
        cmds = _cmds()
        self.axes_root = cmds.group(empty=True, name=AXES_NAME, parent=self.content)
        colors = ((0.9, 0.18, 0.18), (0.2, 0.8, 0.3), (0.2, 0.42, 1.0))
        for index, color in enumerate(colors):
            curve = cmds.curve(
                degree=1,
                point=[(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
                name=f"{AXES_NAME}_{'XYZ'[index]}",
            )
            cmds.parent(curve, self.axes_root, relative=True)
            shape = (cmds.listRelatives(curve, shapes=True, fullPath=True) or [None])[0]
            if shape:
                # VP2 可能忽略 Reference 显示对象的绘制覆盖色；使用 Normal 显示模式，
                # 并同时设置两套受支持的线框颜色属性。
                cmds.setAttr(f"{shape}.overrideEnabled", 1)
                cmds.setAttr(f"{shape}.overrideRGBColors", 1)
                cmds.setAttr(f"{shape}.overrideColorRGB", *color)
                cmds.setAttr(f"{shape}.overrideDisplayType", 0)
                for node in (curve, shape):
                    if cmds.attributeQuery("useObjectColor", node=node, exists=True):
                        cmds.setAttr(f"{node}.useObjectColor", 2)
                    if cmds.attributeQuery("wireColorRGB", node=node, exists=True):
                        cmds.setAttr(f"{node}.wireColorRGB", *color)
                if cmds.attributeQuery("lineWidth", node=shape, exists=True):
                    cmds.setAttr(f"{shape}.lineWidth", 1.0)
            # 锁定变换以免误操作，同时保留 Normal 显示模式下的 RGB 颜色。
            for attr in ("translate", "rotate", "scale"):
                for component in "XYZ":
                    cmds.setAttr(f"{curve}.{attr}{component}", lock=True)
            self._origin_axes.append(curve)
        self._update_origin_axes(self.current_convention())

    def _update_origin_axes(self, convention) -> None:
        """将目标 X/Y/Z 轴嵌入 Maya 显示空间并更新线段两端。"""
        cmds = _cmds()
        from ..core.coord_convention import apply3x3

        for index, curve in enumerate(self._origin_axes):
            basis = tuple(1.0 if component == index else 0.0 for component in range(3))
            direction = apply3x3(convention.viewport_basis, basis)
            for cv, sign in ((0, -1.0), (1, 1.0)):
                point = [sign * self._axis_length * value for value in direction]
                cmds.xform(f"{curve}.cv[{cv}]", objectSpace=True, translation=point)

    def set_origin_axes_visible(self, visible: bool) -> None:
        """显示或隐藏彩色坐标轴，不影响受检网格。"""
        _cmds().setAttr(f"{self.axes_root}.visibility", bool(visible))

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

    def _view_selection(self) -> list[str]:
        """返回当前选择中属于隔离副本的对象/组件。"""
        cmds = _cmds()
        dup_paths = cmds.ls(self.dup, long=True) or []
        if not dup_paths:
            return []
        prefix = dup_paths[0]
        return [
            item
            for item in (cmds.ls(selection=True, long=True, flatten=True) or [])
            if item == prefix or item.startswith(prefix + ".") or item.startswith(prefix + "|")
        ]

    def activate_tool(self, tool: str) -> None:
        """切换到 Maya 标准 Q/W/E/R 工具；实际编辑目标仍由当前选择决定。"""
        contexts = {
            "select": "selectSuperContext",
            "move": "moveSuperContext",
            "rotate": "RotateSuperContext",
            "scale": "scaleSuperContext",
        }
        _cmds().setToolTo(contexts[tool])

    def hide_selection(self) -> bool:
        """隐藏隔离副本中的当前选择，不允许快捷键作用到源场景。"""
        cmds = _cmds()
        selected = self._view_selection()
        if not selected:
            return False
        cmds.hide(selected)
        self._hidden_history.append(selected)
        cmds.refresh()
        return True

    def show_last_hidden(self) -> bool:
        """恢复本视口最近一次隐藏，避免 Maya 全局 ShowLastHidden 影响源场景。"""
        cmds = _cmds()
        while self._hidden_history:
            hidden = [item for item in self._hidden_history.pop() if cmds.objExists(item)]
            if hidden:
                cmds.showHidden(hidden)
                cmds.refresh()
                return True
        return False

    def frame_selection(self) -> None:
        """用专属相机聚焦当前副本选择；无有效选择时聚焦完整副本。"""
        cmds = _cmds()
        selected = self._view_selection()
        previous = cmds.ls(selection=True, long=True, flatten=True) or []
        try:
            cmds.select(selected or [self.dup], replace=True)
            cmds.viewFit(self.camera, animate=False)
        finally:
            if previous:
                cmds.select(previous, replace=True)
            else:
                cmds.select(clear=True)

    def set_source(self, source_mesh: str) -> None:
        """在原面板中换成另一 LOD 的隔离副本，不改变相机与坐标约定。

        relative=True 很重要：新副本需进入 content 的稳定局部预览空间,不能继承 group 的远距偏移。
        """
        cmds = _cmds()
        old_dup = self.dup
        source_matrix = cmds.xform(
            source_mesh, query=True, worldSpace=True, matrix=True
        )
        dup = cmds.duplicate(source_mesh, name=DUP_NAME, returnRootsOnly=True)[0]
        cmds.parent(dup, self.content, relative=True)
        # 首次创建 content 时，副本的世界矩阵会成为其局部基准矩阵。切换时显式
        # 复现这一点，兼容 LOD 源模型位于带变换父组下的情况。
        cmds.xform(dup, matrix=source_matrix, objectSpace=True)
        self.source = source_mesh
        self.dup = dup
        self._axis_length = self._origin_axis_length(source_mesh)
        self._update_origin_axes(self.current_convention())
        self._hidden_history.clear()
        try:
            cmds.delete(old_dup)
        except RuntimeError:
            pass
        # 不调用 _fit_camera：LOD 切换应保留用户当前的 tumble / pan / zoom。
        cmds.refresh()

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
        """切换目标坐标解释并更新视口中的坐标轴。

        模型保持原姿态,只更新当前坐标约定和原点轴;**完全不触碰原始场景网格**。也不影响
        ``show_channel`` 按 face-vertex 索引写颜色的逻辑。
        """
        cmds = _cmds()
        from ..core.coord_convention import CONVENTIONS

        conv = CONVENTIONS[convention_id]
        self._coord_id = convention_id
        self._update_origin_axes(conv)
        cmds.refresh()

    def set_convert_uv(self, enabled: bool) -> None:
        """设置是否随坐标约定同步转换 UV 空间(V→1-V)。只存标志;重着色由窗口驱动(见 window)。"""
        self._convert_uv = bool(enabled)

    def show_channel(
        self, rule, source_view, *, show_values: bool = False, font_size: int = 12,
        value_color: tuple[float, float, float, float] | None = None,
        label_occlusion_culling: bool = True,
    ) -> object:
        """按规则读取源网格通道 → 解码 → 给副本着色 → 刷新;返回 RuleResult(含校验)。

        ``rule`` 来自 ``ui.channels.scalar_rule_for``;``source_view`` 是源网格的
        ``core.mesh_data.MeshData``(从它读原始数据,着色写到副本上)。
        """
        cmds = _cmds()
        from ..core.context import InspectionContext
        from ..core.coord_convention import CONVENTIONS, flip_uv_v
        from ..core.mesh_data import MeshData
        from ..core.types import RuleResult

        channels = {
            role: source_view.read_channel(ch) for role, ch in rule.channel_roles.items()
        }
        # 解码前按当前坐标约定同步转换 UV 空间(UE 的 V→1-V);预览与校验因此一致。
        flip_uv_v(channels, CONVENTIONS[self._coord_id], self._convert_uv)
        decoded = rule.decoder.decode(channels)

        dup_view = MeshData(self.dup)
        ctx = InspectionContext(mesh_name=self.dup)
        info = rule.visualizer.apply(dup_view, decoded, ctx)  # 写副本的显示 color set
        from ..visualize.viewport import ViewportTextVisualizer

        options = {
            "font_size": font_size,
            "parent": self.dup,
            "occlusion_culling": label_occlusion_culling,
        }
        if value_color is not None:
            options["color"] = value_color
        labels = ViewportTextVisualizer(**options)
        if show_values:
            labels.apply(dup_view, decoded, ctx)
        else:
            labels.clear(dup_view, ctx)
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
