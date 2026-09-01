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
        from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - 旧版 Maya
        from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]
    return QtCore, QtGui, QtWidgets


def _wrap_instance():
    try:
        from shiboken6 import wrapInstance  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover
        from shiboken2 import wrapInstance  # type: ignore[import-not-found]
    return wrapInstance


def _maya_main_window():
    import maya.OpenMayaUI as omui  # type: ignore[import-not-found]

    _, _, QtWidgets = _qt()
    ptr = omui.MQtUtil.mainWindow()
    return _wrap_instance()(int(ptr), QtWidgets.QWidget) if ptr else None


def _purge_leftovers() -> None:
    """按已知名字清理上一次残留:窗口部件、孤儿检查面板、副本组、专属相机。

    工具架按钮每次点击都会重载模块,故不能依赖 Python 引用,只能按名字清理。
    """
    import maya.cmds as cmds  # type: ignore[import-not-found]

    from .viewport_panel import CAM_NAME, GROUP_NAME

    _, _, QtWidgets = _qt()

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
    QtCore, QtGui, QtWidgets = _qt()

    from ..core.mesh_data import MeshData
    from ..core.registry import PROFILES
    from ..report import build_report
    from ..core.coord_convention import CONVENTIONS
    from ..visualize.base import RAMPS
    from ..visualize.viewport import DEFAULT_LABEL_COLOR
    from .axis_indicator import make_axis_indicator
    from .channels import scalar_rule_for
    from .viewport_panel import IsolatedMeshView

    class InspectorWindow(QtWidgets.QMainWindow):
        """FBX 资产检查窗口(挂在 Maya 主窗口下的浮动窗口)。"""

        def __init__(self, mesh_name: str, lod_meshes=None, parent=None) -> None:
            super().__init__(parent)
            self.setObjectName(_OBJECT_NAME)
            self.setWindowFlags(QtCore.Qt.Window)
            self.setWindowTitle(f"FBX Inspector — {mesh_name}")
            self.resize(720, 640)

            self._lod_meshes = dict(lod_meshes or {0: mesh_name})
            self._lod_levels = sorted(self._lod_meshes)
            self._mesh_name = self._lod_meshes[self._lod_levels[0]]
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

            preset_row = QtWidgets.QHBoxLayout()
            preset_row.addWidget(QtWidgets.QLabel("检查预设"))
            self._preset_combo = QtWidgets.QComboBox()
            preset_row.addWidget(self._preset_combo, stretch=1)
            self._run_preset_button = QtWidgets.QPushButton("一键执行全部规则")
            preset_row.addWidget(self._run_preset_button)
            root.addLayout(preset_row)
            self._preset_description = QtWidgets.QLabel()
            self._preset_description.setWordWrap(True)
            root.addWidget(self._preset_description)
            self._populate_presets(PROFILES)
            self._preset_combo.currentIndexChanged.connect(self._update_preset_description)
            self._run_preset_button.clicked.connect(self._run_preset)
            self._update_preset_description()

            lod_row = QtWidgets.QHBoxLayout()
            lod_row.addWidget(QtWidgets.QLabel("LOD"))
            self._lod_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self._lod_slider.setRange(0, len(self._lod_levels) - 1)
            self._lod_slider.setSingleStep(1)
            self._lod_slider.setPageStep(1)
            self._lod_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
            self._lod_slider.setTickInterval(1)
            self._lod_slider.setEnabled(len(self._lod_levels) > 1)
            lod_row.addWidget(self._lod_slider, stretch=1)
            self._lod_label = QtWidgets.QLabel(f"LOD{self._lod_levels[0]}")
            self._lod_label.setMinimumWidth(48)
            lod_row.addWidget(self._lod_label)
            root.addLayout(lod_row)
            self._lod_slider.valueChanged.connect(self._change_lod)

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
            self._label_occlusion = QtWidgets.QCheckBox("标签遮挡剔除")
            self._label_occlusion.setChecked(True)
            self._label_occlusion.setToolTip("仅绘制当前相机可见的顶点数值标签")
            opts.addWidget(self._label_occlusion)
            opts.addWidget(QtWidgets.QLabel("颜色"))
            self._value_color = QtGui.QColor.fromRgbF(*DEFAULT_LABEL_COLOR)
            self._color_button = QtWidgets.QPushButton()
            self._color_button.setFixedSize(28, 22)
            self._color_button.setToolTip("选择数值标签颜色")
            self._update_color_button()
            opts.addWidget(self._color_button)
            opts.addWidget(QtWidgets.QLabel("字号"))
            self._font_size = QtWidgets.QSpinBox()
            self._font_size.setRange(6, 48)
            self._font_size.setValue(12)
            opts.addWidget(self._font_size)
            opts.addStretch(1)
            root.addLayout(opts)

            # 坐标系:模型姿态不变,目标引擎的轴方向/手性由视口坐标轴表达。
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
            self._show_origin_axes = QtWidgets.QCheckBox("显示原点坐标轴")
            self._show_origin_axes.setChecked(True)
            coord_row.addWidget(self._show_origin_axes)
            coord_row.addStretch(1)
            root.addLayout(coord_row)
            self._coord_combo.currentIndexChanged.connect(self._apply_coord)
            self._convert_uv.stateChanged.connect(self._apply_uv_convert)
            self._show_origin_axes.stateChanged.connect(self._apply_origin_axes)

            for w in (self._ramp_combo, self._curve_combo):
                w.currentIndexChanged.connect(self._reapply)
            self._normalize.stateChanged.connect(self._reapply)
            self._show_values.stateChanged.connect(self._reapply)
            self._label_occlusion.stateChanged.connect(self._reapply)
            self._color_button.clicked.connect(self._choose_value_color)
            self._font_size.valueChanged.connect(self._reapply)

            root.addWidget(self._view.widget, stretch=1)

            # Maya 的 modelPanel 会先于普通 QShortcut 接管按键，且它内嵌后不保证成为
            # Qt 焦点子控件。因此在应用事件入口截获“鼠标位于本视口”时的核心热键。
            callbacks = {
                QtCore.Qt.Key_Q: lambda: self._view.activate_tool("select"),
                QtCore.Qt.Key_W: lambda: self._view.activate_tool("move"),
                QtCore.Qt.Key_E: lambda: self._view.activate_tool("rotate"),
                QtCore.Qt.Key_R: lambda: self._view.activate_tool("scale"),
                QtCore.Qt.Key_F: self._view.frame_selection,
                QtCore.Qt.Key_H: self._view.hide_selection,
            }

            class ViewportHotkeyFilter(QtCore.QObject):
                def eventFilter(filter_self, watched, event):  # noqa: N802
                    if event.type() != QtCore.QEvent.KeyPress or not self.isActiveWindow():
                        return False
                    local_cursor = self._view.widget.mapFromGlobal(QtGui.QCursor.pos())
                    if not self._view.widget.rect().contains(local_cursor):
                        return False
                    modifiers = event.modifiers()
                    if event.key() == QtCore.Qt.Key_H and modifiers == QtCore.Qt.ShiftModifier:
                        if not event.isAutoRepeat():
                            self._view.show_last_hidden()
                        return True
                    if modifiers != QtCore.Qt.NoModifier:
                        return False
                    callback = callbacks.get(event.key())
                    if callback is None:
                        return False
                    if not event.isAutoRepeat():
                        callback()
                    return True

            self._viewport_hotkey_filter = ViewportHotkeyFilter(self)
            QtWidgets.QApplication.instance().installEventFilter(
                self._viewport_hotkey_filter
            )

            shortcut_help = QtWidgets.QLabel(
                "视口快捷键：Q 选择　W 移动　E 旋转　R 缩放　H 隐藏　Shift+H 恢复　F 聚焦"
            )
            shortcut_help.setStyleSheet("color: #999;")
            root.addWidget(shortcut_help)

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
            current_cs = self._cs_combo.currentText()
            current_uv = self._uv_combo.currentText()
            self._cs_combo.clear()
            self._uv_combo.clear()
            self._cs_combo.addItems(self._source_view.color_set_names())
            self._uv_combo.addItems(self._source_view.uv_set_names())
            for combo, previous in (
                (self._cs_combo, current_cs),
                (self._uv_combo, current_uv),
            ):
                index = combo.findText(previous)
                if index >= 0:
                    combo.setCurrentIndex(index)

        def _change_lod(self, slider_index) -> None:
            level = self._lod_levels[slider_index]
            mesh_name = self._lod_meshes[level]
            self._view.set_source(mesh_name)
            self._mesh_name = mesh_name
            self._source_view = MeshData(mesh_name)
            self._lod_label.setText(f"LOD{level}")
            self.setWindowTitle(f"FBX Inspector — {mesh_name}")
            self._populate_channels()
            if self._current is not None:
                source, _, component = self._current
                combo = self._combo_for(source)
                if combo.currentText():
                    self._current = (source, combo.currentText(), component)
                    self._apply()
                else:
                    self._current = None
                    self._range_label.setText("min / max：—")

        def _populate_presets(self, registry) -> None:
            profiles = registry.all()
            ordered = sorted(
                profiles.values(),
                key=lambda profile: (profile.id != "default", profile.display_name),
            )
            for profile in ordered:
                self._preset_combo.addItem(profile.display_name, userData=profile.id)

        def _selected_profile(self):
            profile_id = self._preset_combo.currentData()
            return PROFILES.get(profile_id) if profile_id else None

        def _update_preset_description(self, *args) -> None:
            profile = self._selected_profile()
            self._preset_description.setText(profile.description if profile else "")

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

        def _run_preset(self, *args) -> None:
            profile = self._selected_profile()
            if profile is None:
                self._report.setPlainText("没有可执行的检查预设。")
                return
            if not profile.matches(self._mesh_name):
                self._report.setPlainText(
                    f"预设“{profile.display_name}”不适用于资产 {self._mesh_name}。"
                )
                return

            # 前置检查覆盖资产的全部 LOD；失败时不进入可视化阶段。
            lod_views = {
                level: MeshData(mesh_name)
                for level, mesh_name in self._lod_meshes.items()
            }
            results = profile.run_preflight(lod_views)
            failures = []
            if any(result.error_count for result in results):
                self._report.setPlainText(
                    build_report(self._mesh_name, results).to_text()
                )
                return
            for rule in profile.rules:
                try:
                    results.append(
                        self._view.show_channel(
                            rule,
                            self._source_view,
                            show_values=self._show_values.isChecked(),
                            font_size=self._font_size.value(),
                            value_color=self._value_color.getRgbF(),
                            label_occlusion_culling=self._label_occlusion.isChecked(),
                        )
                    )
                except Exception as exc:  # 单条规则失败不阻断同一预设中的其余规则
                    failures.append(f"[规则 {rule.id}] 执行失败：{exc}")

            # 预设中的每个可视化器都会把自己的 color set 设为 current，最后一条规则
            # 因而会暂时占据视口。恢复执行前手动选中的通道，但不要用它覆盖预设汇总报告。
            if self._current is not None:
                try:
                    self._apply(update_report=False)
                except Exception as exc:
                    failures.append(f"[恢复当前通道] 刷新失败：{exc}")

            text = build_report(self._mesh_name, results).to_text() if results else ""
            if failures:
                text = "\n".join(filter(None, [text, *failures]))
            self._report.setPlainText(text or "该预设没有规则。")

        def _choose_value_color(self) -> None:
            color = QtWidgets.QColorDialog.getColor(
                self._value_color, self, "选择数值标签颜色"
            )
            if color.isValid():
                self._value_color = color
                self._update_color_button()
                self._reapply()

        def _update_color_button(self) -> None:
            self._color_button.setStyleSheet(
                "QPushButton { background-color: %s; border: 1px solid #777; }"
                % self._value_color.name()
            )

        def _apply_coord(self, *args) -> None:
            # UV 空间随坐标约定变化:UE 的 V→1-V 需要重跑当前 UV 通道的预览与校验。
            self._view.set_coord_convention(self._coord_combo.currentData())
            if self._current is not None and self._current[0] is SourceType.UV_SET:
                self._apply()

        def _apply_uv_convert(self, *args) -> None:
            self._view.set_convert_uv(self._convert_uv.isChecked())
            if self._current is not None and self._current[0] is SourceType.UV_SET:
                self._apply()

        def _apply_origin_axes(self, *args) -> None:
            self._view.set_origin_axes_visible(self._show_origin_axes.isChecked())

        def _apply(self, *, update_report: bool = True) -> None:
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
                value_color=self._value_color.getRgbF(),
                label_occlusion_culling=self._label_occlusion.isChecked(),
            )
            self._update_range_label(result.viz_info)
            if update_report:
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

    # 内置默认预设 + 用户目录中的额外预设。示例 Profile 不进入正式预设列表。
    from .. import plugins
    from ..presets import default_profile  # noqa: F401

    plugins.discover(include_examples=False)

    if not mesh_name:
        sel = cmds.ls(selection=True, long=True)
        if not sel:
            raise RuntimeError("请先选中一个网格,或以 open_inspector('meshName') 指定。")
        mesh_name = sel[0]

    from .lod import discover_lod_meshes

    lod_meshes = discover_lod_meshes(mesh_name)
    first_mesh = lod_meshes[sorted(lod_meshes)[0]]
    _purge_leftovers()  # 清掉上一次的窗口/面板/副本/相机(按名字,不依赖 Python 引用)

    cls = _make_window_class()
    win = cls(first_mesh, lod_meshes=lod_meshes, parent=_maya_main_window())
    win.show()
    return win
