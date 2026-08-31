"""独立检查窗口(基于 PySide6 / Qt6,仅 Maya 2025)。

窗口内嵌一个**隔离的 Maya 视口**(见 ``viewport_panel.IsolatedMeshView``),里面只显示目标网格
的一份临时副本。像 UV 编辑器那样按通道查看:点 R/G/B/A 看 color set 的对应分量,点 U/V 看 UV set
的对应分量;可调色带 / 归一化 / chramp 式曲线。着色只发生在副本上,**主视口/场景观感始终不变**。

窗口是挂在 Maya 主窗口下的**普通浮动窗口**(不走 workspaceControl/dockable),以避免可停靠控件的
"同名不唯一"冲突——尤其是工具架按钮每次点击都会重载模块、丢失上一次的 Python 引用。因此重开前
一律按**已知名字**清理上一次的残留(窗口、孤儿面板、副本组、相机)。

为使本模块在无 Maya / 无 Qt 环境也能被 import,窗口类在函数内惰性定义,Maya / PySide6 仅在真正
开窗时导入。⚠️ 窗口整体只能在 Maya 2025 GUI 内手测(``cmds.modelPanel`` 需要 GUI)。
"""

from __future__ import annotations

from ..core.channel import SourceType
from ..core.remap import Ramp

_OBJECT_NAME = "FbxInspectorWindow"

# 曲线预设:显示名 → 生成 Ramp 的工厂;"linear" 用 None 表示不做曲线。
_CURVES = {
    "linear": None,
    "quadratic": Ramp.quadratic,
    "gamma 2.2": lambda: Ramp.gamma(2.2),
    "smoothstep": Ramp.smoothstep,
}

_COMPONENTS = {
    SourceType.COLOR_SET: ("R", "G", "B", "A"),
    SourceType.UV_SET: ("U", "V"),
}


def _qt():
    try:
        from PySide6 import QtCore, QtWidgets  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - 旧版 Maya
        from PySide2 import QtCore, QtWidgets  # type: ignore[import-not-found]
    return QtCore, QtWidgets


def _wrap_instance():
    try:
        from shiboken6 import wrapInstance  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover
        from shiboken2 import wrapInstance  # type: ignore[import-not-found]
    return wrapInstance


def _maya_main_window():
    import maya.OpenMayaUI as omui  # type: ignore[import-not-found]

    _, QtWidgets = _qt()
    ptr = omui.MQtUtil.mainWindow()
    return _wrap_instance()(int(ptr), QtWidgets.QWidget) if ptr else None


def _purge_leftovers() -> None:
    """按已知名字清理上一次残留:窗口部件、孤儿检查面板、副本组、专属相机。

    工具架按钮每次点击都会重载模块,故不能依赖 Python 引用,只能按名字清理。
    """
    import maya.cmds as cmds  # type: ignore[import-not-found]

    from .viewport_panel import CAM_NAME, GROUP_NAME

    _, QtWidgets = _qt()

    # 0) 旧版可停靠实现残留的 workspaceControl(Maya 会跨会话保存,需主动清掉)
    legacy_ws = _OBJECT_NAME + "WorkspaceControl"
    if cmds.workspaceControl(legacy_ws, exists=True):
        try:
            cmds.deleteUI(legacy_ws, control=True)
        except RuntimeError:
            pass

    # 1) 旧窗口部件(可能是重载前的旧类实例,按 objectName 查找)
    main = _maya_main_window()
    if main is not None:
        for w in main.findChildren(QtWidgets.QWidget, _OBJECT_NAME):
            try:
                w.close()
                w.deleteLater()
            except RuntimeError:
                pass

    # 2) 孤儿检查面板(相机名匹配本工具的专属相机)
    for panel in cmds.getPanel(type="modelPanel") or []:
        try:
            cam = cmds.modelPanel(panel, query=True, camera=True)
        except RuntimeError:
            continue
        if cam and CAM_NAME in cam:
            try:
                cmds.deleteUI(panel, panel=True)
            except RuntimeError:
                pass

    # 3) 残留的副本组与相机
    for node in (GROUP_NAME, CAM_NAME):
        if cmds.objExists(node):
            try:
                cmds.delete(node)
            except RuntimeError:
                pass


def _make_window_class():
    QtCore, QtWidgets = _qt()

    from ..core.mesh_data import MeshData
    from ..report import build_report
    from ..core.coord_convention import CONVENTIONS
    from ..visualize.base import RAMPS
    from .axis_indicator import make_axis_indicator
    from .channels import scalar_rule_for
    from .viewport_panel import IsolatedMeshView

    class InspectorWindow(QtWidgets.QMainWindow):
        """FBX 资产检查窗口(挂在 Maya 主窗口下的浮动窗口)。"""

        def __init__(self, mesh_name: str, parent=None) -> None:
            super().__init__(parent)
            self.setObjectName(_OBJECT_NAME)
            self.setWindowFlags(QtCore.Qt.Window)
            self.setWindowTitle(f"FBX Inspector — {mesh_name}")
            self.resize(720, 640)

            self._mesh_name = mesh_name
            self._source_view = MeshData(mesh_name)
            self._view = IsolatedMeshView(mesh_name)
            self._current = None  # (source, set_name, component)

            self._build_ui(RAMPS)
            self._populate_channels()

        # —— 构建控件 ——
        def _build_ui(self, ramps) -> None:
            central = QtWidgets.QWidget()
            self.setCentralWidget(central)
            root = QtWidgets.QVBoxLayout(central)

            self._cs_combo = QtWidgets.QComboBox()
            self._uv_combo = QtWidgets.QComboBox()
            root.addLayout(
                self._channel_row("Color Set", self._cs_combo, SourceType.COLOR_SET)
            )
            root.addLayout(
                self._channel_row("UV Set", self._uv_combo, SourceType.UV_SET)
            )

            opts = QtWidgets.QHBoxLayout()
            opts.addWidget(QtWidgets.QLabel("色带"))
            self._ramp_combo = QtWidgets.QComboBox()
            self._ramp_combo.addItems(sorted(ramps))
            if "grayscale" in ramps:
                self._ramp_combo.setCurrentText("grayscale")
            opts.addWidget(self._ramp_combo)
            self._normalize = QtWidgets.QCheckBox("归一化")
            self._normalize.setChecked(True)
            opts.addWidget(self._normalize)
            # 紧跟"归一化"显示当前通道的 min/max,标明颜色所依据的归一化区间。
            self._range_label = QtWidgets.QLabel("min / max：—")
            opts.addWidget(self._range_label)
            opts.addWidget(QtWidgets.QLabel("曲线"))
            self._curve_combo = QtWidgets.QComboBox()
            self._curve_combo.addItems(list(_CURVES))
            opts.addWidget(self._curve_combo)
            self._show_values = QtWidgets.QCheckBox("显示数值")
            opts.addWidget(self._show_values)
            opts.addWidget(QtWidgets.QLabel("字号"))
            self._font_size = QtWidgets.QSpinBox()
            self._font_size.setRange(6, 48)
            self._font_size.setValue(12)
            opts.addWidget(self._font_size)
            opts.addStretch(1)
            root.addLayout(opts)

            # 坐标系:切换后隔离视口里的副本会摆成目标引擎导入后的姿态(如 UE 的 Z-up 左手)。
            coord_row = QtWidgets.QHBoxLayout()
            coord_row.addWidget(QtWidgets.QLabel("坐标系"))
            self._coord_combo = QtWidgets.QComboBox()
            for cid, conv in CONVENTIONS.items():
                self._coord_combo.addItem(conv.label, userData=cid)
            coord_row.addWidget(self._coord_combo)
            # UV 空间是否随坐标系同步转换(UE 导入器对 V 做 V→1-V);默认开。
            self._convert_uv = QtWidgets.QCheckBox("转换 UV 空间 (V→1-V)")
            self._convert_uv.setChecked(True)
            coord_row.addWidget(self._convert_uv)
            coord_row.addStretch(1)
            root.addLayout(coord_row)
            self._coord_combo.currentIndexChanged.connect(self._apply_coord)
            self._convert_uv.stateChanged.connect(self._apply_uv_convert)

            for w in (self._ramp_combo, self._curve_combo):
                w.currentIndexChanged.connect(self._reapply)
            self._normalize.stateChanged.connect(self._reapply)
            self._show_values.stateChanged.connect(self._reapply)
            self._font_size.valueChanged.connect(self._reapply)

            root.addWidget(self._view.widget, stretch=1)

            # 右上角方向指示器:作为视口 QWidget 的子控件叠在其上,随镜头/约定实时刷新。
            indicator_cls = make_axis_indicator(
                self._view.camera_view_rotation, self._view.current_convention
            )
            self._indicator = indicator_cls(self._view.widget)
            self._indicator.show()

            self._report = QtWidgets.QPlainTextEdit()
            self._report.setReadOnly(True)
            self._report.setMaximumHeight(160)
            root.addWidget(self._report)

        def _channel_row(self, label, combo, source):
            row = QtWidgets.QHBoxLayout()
            row.addWidget(QtWidgets.QLabel(label))
            row.addWidget(combo, stretch=1)
            for comp in _COMPONENTS[source]:
                btn = QtWidgets.QPushButton(comp)
                btn.setFixedWidth(32)
                btn.clicked.connect(
                    lambda _=False, s=source, c=comp: self._select(s, c)
                )
                row.addWidget(btn)
            return row

        def _populate_channels(self) -> None:
            self._cs_combo.addItems(self._source_view.color_set_names())
            self._uv_combo.addItems(self._source_view.uv_set_names())

        # —— 交互 ——
        def _combo_for(self, source):
            return self._cs_combo if source is SourceType.COLOR_SET else self._uv_combo

        def _curve(self):
            factory = _CURVES[self._curve_combo.currentText()]
            return factory() if factory else None

        def _select(self, source, component) -> None:
            combo = self._combo_for(source)
            set_name = combo.currentText()
            if not set_name:
                self._report.setPlainText(f"网格上没有可用的 {source.value}。")
                return
            self._current = (source, set_name, component)
            self._apply()

        def _reapply(self, *args) -> None:
            if self._current is not None:
                self._apply()

        def _apply_coord(self, *args) -> None:
            # 副本姿态与 UV 空间都随坐标约定变化:UV 的 V 现按 UE 的 V→1-V 同步转换,故约定切换后
            # 若当前正显示 UV 通道,需重跑 _apply 让预览/校验跟上;非 UV 通道的颜色仍与世界变换无关。
            self._view.set_coord_convention(self._coord_combo.currentData())
            if self._current is not None and self._current[0] is SourceType.UV_SET:
                self._apply()

        def _apply_uv_convert(self, *args) -> None:
            self._view.set_convert_uv(self._convert_uv.isChecked())
            if self._current is not None and self._current[0] is SourceType.UV_SET:
                self._apply()

        def _apply(self) -> None:
            source, set_name, component = self._current
            rule = scalar_rule_for(
                source,
                set_name,
                component,
                ramp=self._ramp_combo.currentText(),
                curve=self._curve(),
                normalize=self._normalize.isChecked(),
            )
            result = self._view.show_channel(
                rule,
                self._source_view,
                show_values=self._show_values.isChecked(),
                font_size=self._font_size.value(),
            )
            self._update_range_label(result.viz_info)
            report = build_report(self._mesh_name, [result])
            self._report.setPlainText(report.to_text())

        def _update_range_label(self, info) -> None:
            """把当前通道的 min/max 写到"归一化"旁的标签上。"""
            if info is None or info.data_min is None:
                self._range_label.setText("min / max：—")
                return
            prefix = "归一化区间" if info.normalized else "数据区间"
            self._range_label.setText(
                f"{prefix}：min={info.data_min:.4g}  max={info.data_max:.4g}"
            )

        # —— 生命周期 ——
        def closeEvent(self, event) -> None:  # noqa: N802 - Qt 命名
            try:
                self._view.cleanup()
            finally:
                super().closeEvent(event)

    return InspectorWindow


def open_inspector(mesh_name: str = ""):
    """在 Maya 内打开检查窗口。未传网格名时取当前选中的网格。"""
    import maya.cmds as cmds  # type: ignore[import-not-found]

    if not mesh_name:
        sel = cmds.ls(selection=True, long=True)
        if not sel:
            raise RuntimeError("请先选中一个网格,或以 open_inspector('meshName') 指定。")
        mesh_name = sel[0]

    _purge_leftovers()  # 清掉上一次的窗口/面板/副本/相机(按名字,不依赖 Python 引用)

    cls = _make_window_class()
    win = cls(mesh_name, parent=_maya_main_window())
    win.show()
    return win
