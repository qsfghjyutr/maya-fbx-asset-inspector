"""右上角方向指示器(Qt 遮罩层)。

在隔离视口右上角画一个固定大小的小方块,里面是三色坐标轴,**随镜头 tumble 实时转动**,并**反映
当前坐标约定**(切到 UE 时轴的朝向会真的转过去,不只是文字标签变)——类似 Blender/Unity 的导航
gizmo。Maya 自带的角落轴永远显示 Maya 世界(Y-up),无法表达 UE 约定,故自绘。

颜色和标签始终绑定 X/Y/Z 轴身份:X 红 / Y 绿 / Z 蓝。切换坐标约定时只变换三根箭头的方向;
若方向和标签同时交换,UE 的镜像会被视觉抵消,使左手系错误地显示成右手系。

分两层:
- ``project_axes`` / ``ProjectedAxis`` 是**纯函数**(只依赖 core.coord_convention),把"世界→相机旋转 +
  坐标约定"投影成屏幕方向,可脱离 Maya / Qt 单测。
- ``make_axis_indicator`` 惰性导入 PySide6,返回一个每帧重绘、自定位到右上角的 QWidget。绘制与相机
  朝向查询需在 Maya GUI 内手测。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.coord_convention import CoordConvention, Matrix3, apply3x3

# 轴基色(0-255),按**引擎轴身份**(标签字母)固定,不按模型局部轴下标固定——
# X 永远红、Y 永远绿、Z 永远蓝。这样切换坐标约定时"谁是 Up"的颜色会跟着变
# (Maya 下 Up 是 Y=绿,切到 UE 后 Up 变成 Z=蓝),可从颜色直接分辨切换是否生效。
_AXIS_COLOR_BY_LETTER: dict[str, tuple[int, int, int]] = {
    "X": (230, 66, 66),
    "Y": (86, 196, 108),
    "Z": (74, 130, 240),
}

_AXIS_NAMES = ("X", "Y", "Z")


def _axis_letter(label: str) -> str:
    """从 ``axis_label_map`` 的标签(如 ``"-Z (Up)"``)里取出裸字母(``"Z"``)。

    符号(负轴)不影响颜色——负 Z 跟正 Z 是"同一根引擎轴",都该显示蓝色;只有字母本身
    (X/Y/Z)决定颜色。
    """
    base = label.split(" ")[0]  # 去掉 " (Up)"
    return base.lstrip("-")


@dataclass
class ProjectedAxis:
    """一根轴投影到指示器平面后的绘制信息。"""

    label: str  # 引擎轴名(可能带号与 "(Up)"),如 "Z (Up)"
    color: tuple[int, int, int]
    dx: float  # 屏幕右为正(单位向量分量)
    dy: float  # 屏幕上为正
    depth: float  # 相机局部 z:越大越靠近观察者,用于前后遮挡排序


def project_axes(view_rot: Matrix3, convention: CoordConvention) -> list[ProjectedAxis]:
    """把模型局部三根轴(按当前约定变换后)投影到指示器平面。

    ``view_rot`` 是"世界→相机"旋转(见 core.coord_convention.view_rotation_from_matrix)。
    每根 Maya 局部轴先经约定矩阵变到世界方向(与视口里副本的姿态一致)再投影到相机局部系——
    切换约定时方向真的会变;颜色按 ``axis_label_map`` 给出的**引擎轴身份**取(不是局部轴下标),
    于是指示器与被变换的模型始终同步,切换约定时箭头会转动**且**当前代表 Up 的那根箭头颜色
    也会变成对应引擎轴的颜色(如 Maya 下 Up=局部 Y 显绿色,切到 UE 后 Up=局部 Z 显蓝色)。
    """
    out: list[ProjectedAxis] = []
    for i in range(3):
        basis = tuple(1.0 if j == i else 0.0 for j in range(3))
        world_dir = convention.apply(basis)  # type: ignore[arg-type]
        cam = apply3x3(view_rot, world_dir)
        # Keep the original axis identity after transforming its direction.
        # Remapping both direction and label would visually cancel UE's mirror.
        axis_name = _AXIS_NAMES[i]
        label = f"{axis_name} (Up)" if axis_name == convention.up_axis else axis_name
        out.append(
            ProjectedAxis(
                label=label,
                color=_AXIS_COLOR_BY_LETTER[_axis_letter(label)],
                dx=cam[0],
                dy=cam[1],
                depth=cam[2],
            )
        )
    return out


def short_label(label: str) -> str:
    """把 ``axis_label_map`` 的完整标签(如 ``"Z (Up)"`` / ``"-Y"``)压成指示器上要画的短文字。

    保留符号(负轴,如 "-Y")和 "Up" 标记——"Up" 是切换坐标约定时最该变化的信息:
    MAYA_TO_UE 只是把 Y/Z 互换位置,单看字母切换前后不变,必须靠 "Up" 才能看出当前的上方向。
    抽成纯函数以便单测覆盖。
    """
    base = label.split(" ")[0]  # 保留符号,如 "-Y"
    return f"{base}↑" if "Up" in label else base


def make_axis_indicator(get_view_rot, get_convention, size: int = 160):
    """构造方向指示器 QWidget(惰性导入 Qt)。

    ``get_view_rot() -> Matrix3`` 与 ``get_convention() -> CoordConvention`` 由调用方(隔离视口)
    提供,widget 每帧调用它们取最新镜头姿态与约定,故 tumble / 切约定都会即时反映。``size`` 是
    小窗边长(像素);线宽/圆点/字号都按它等比缩放,放大不会只是留白变大、文字还是那么小。
    """
    try:
        from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - 旧版 Maya
        from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore[import-not-found]

    class AxisIndicator(QtWidgets.QWidget):
        """右上角固定小窗:三色轴 gizmo,随镜头转动。"""

        _MARGIN = 10  # 距父控件右/上边的像素

        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self._get_view_rot = get_view_rot
            self._get_convention = get_convention
            self.setFixedSize(size, size)
            # 不拦截鼠标,视口交互(tumble/框选)照常穿透到下面的 Maya 面板。
            self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            # 定时重绘 + 自定位:tumble 镜头时指示器也持续跟随。
            self._timer = QtCore.QTimer(self)
            self._timer.setInterval(50)  # ~20fps,足够跟手且开销可忽略
            self._timer.timeout.connect(self._tick)
            self._timer.start()

        def _tick(self) -> None:
            self._reposition()
            self.raise_()  # 保持在 Maya 视口之上
            self.update()

        def _reposition(self) -> None:
            p = self.parent()
            if p is not None:
                self.move(p.width() - self.width() - self._MARGIN, self._MARGIN)

        def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
            try:
                axes = project_axes(self._get_view_rot(), self._get_convention())
            except Exception:  # noqa: BLE001 - 取不到镜头姿态时安静跳过本帧
                return

            s = self.width()  # 边长;下面元素尺寸都按它等比缩放
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

            # 半透明深色圆角底,保证在任何视口背景上都读得清。
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(30, 30, 30, 170))
            painter.drawRoundedRect(self.rect(), s * 0.06, s * 0.06)

            font = painter.font()
            font.setPointSizeF(max(9.0, s * 0.10))
            font.setBold(True)
            painter.setFont(font)

            cx, cy = s / 2.0, s / 2.0
            label_margin = s * 0.16  # 给标签留出的边距
            radius = s / 2.0 - label_margin
            dot_r = s * 0.028
            pen_w = max(2.0, s * 0.02)
            label_box = s * 0.22

            # 后面的轴先画,前面的后画,形成前后遮挡感。
            for ax in sorted(axes, key=lambda a: a.depth):
                ex = cx + ax.dx * radius
                ey = cy - ax.dy * radius  # Qt 的 y 向下,取负让"上"在屏幕上方
                col = QtGui.QColor(*ax.color)
                pen = QtGui.QPen(col, pen_w)
                painter.setPen(pen)
                painter.drawLine(QtCore.QPointF(cx, cy), QtCore.QPointF(ex, ey))
                painter.setBrush(col)
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(QtCore.QPointF(ex, ey), dot_r, dot_r)
                painter.setPen(QtGui.QColor(240, 240, 240))
                painter.drawText(
                    QtCore.QRectF(ex - label_box / 2, ey - label_box * 0.9, label_box, label_box * 0.7),
                    QtCore.Qt.AlignCenter,
                    short_label(ax.label),
                )
            painter.end()

    return AxisIndicator


__all__ = ["ProjectedAxis", "project_axes", "short_label", "make_axis_indicator"]
