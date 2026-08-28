"""ui/axis_indicator.py 纯投影逻辑的单测(无需 Maya / Qt)。

只测 project_axes 与 view_rotation_from_matrix 这层纯数学;Qt 绘制与相机查询在 Maya GUI 手测。
"""

from __future__ import annotations

from fbx_inspector.core.coord_convention import (
    CONVENTIONS,
    view_rotation_from_matrix,
)
from fbx_inspector.ui.axis_indicator import project_axes, short_label

# 单位相机(无旋转、位于 +Z 看向 -Z)的世界矩阵:前 3x3 为单位阵。
_IDENTITY_M16 = [
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 10.0, 1.0,
]


def _by_letter(axes):
    """按标签首字母归类,便于断言。"""
    return {a.label.split(" ")[0].lstrip("-"): a for a in axes}


def test_view_rotation_from_matrix_takes_upper_left_3x3():
    vr = view_rotation_from_matrix(_IDENTITY_M16)
    assert vr == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def test_maya_axes_project_to_screen_basis():
    vr = view_rotation_from_matrix(_IDENTITY_M16)
    axes = _by_letter(project_axes(vr, CONVENTIONS["maya"]))
    # X → 屏幕右,Y → 屏幕上,Z → 指向观察者(dx=dy=0,depth>0)
    assert (round(axes["X"].dx), round(axes["X"].dy)) == (1, 0)
    assert (round(axes["Y"].dx), round(axes["Y"].dy)) == (0, 1)
    assert round(axes["Z"].dx) == 0 and round(axes["Z"].dy) == 0
    assert axes["Z"].depth > 0


def test_axis_colors_follow_engine_axis_identity_not_local_axis():
    """颜色跟着当前代表的引擎轴身份(标签字母 X/Y/Z),不跟着模型局部轴下标——切换约定后,
    同一根局部轴改代表了别的引擎轴,其颜色必须随之改变,才能从视觉上分辨切换已生效。
    """
    vr = view_rotation_from_matrix(_IDENTITY_M16)
    maya_axes = project_axes(vr, CONVENTIONS["maya"])
    ue_axes = project_axes(vr, CONVENTIONS["ue"])

    # 局部 X 在两种约定下都还是引擎 X → 颜色不变(红)。
    assert maya_axes[0].color == ue_axes[0].color == (230, 66, 66)
    # 局部 Y:Maya 下代表引擎 Y(绿),UE 下代表引擎 Z(蓝)→ 颜色必须变。
    assert maya_axes[1].color == (86, 196, 108)
    assert ue_axes[1].color == (74, 130, 240)
    # 局部 Z:Maya 下代表引擎 Z(蓝),UE 下代表引擎 Y(绿)→ 颜色必须变。
    assert maya_axes[2].color == (74, 130, 240)
    assert ue_axes[2].color == (86, 196, 108)


def test_ue_convention_actually_rotates_the_arrows():
    """切到 UE 后,箭头方向必须真的变了(不能只是标签文字变而箭头停在原处)。"""
    vr = view_rotation_from_matrix(_IDENTITY_M16)
    maya_axes = project_axes(vr, CONVENTIONS["maya"])
    ue_axes = project_axes(vr, CONVENTIONS["ue"])

    # 局部 Y(下标 1):Maya 下指屏幕上、UE 下指向观察者(模型原本的"上"现在朝 +Z)。
    assert (round(maya_axes[1].dx), round(maya_axes[1].dy)) == (0, 1)
    assert round(ue_axes[1].dx) == 0 and round(ue_axes[1].dy) == 0
    assert ue_axes[1].depth > 0
    assert "Up" in ue_axes[1].label

    # 局部 Z(下标 2):Maya 下指向观察者、UE 下指屏幕上。
    assert round(maya_axes[2].dx) == 0 and round(maya_axes[2].dy) == 0
    assert (round(ue_axes[2].dx), round(ue_axes[2].dy)) == (0, 1)

    # 局部 X(下标 0)在两种约定下都不变。
    assert (round(maya_axes[0].dx), round(maya_axes[0].dy)) == (1, 0)
    assert (round(ue_axes[0].dx), round(ue_axes[0].dy)) == (1, 0)


def test_short_label_keeps_up_marker():
    """回归锁点:短标签必须保留 "Up" 信息,否则切换约定时看不出"谁换成了上方向"
    ——MAYA_TO_UE 只是 Y/Z 换位,单看字母本身切换前后还是那几个,全靠这个标记分辨。
    """
    assert short_label("X") == "X"
    assert short_label("Y (Up)") == "Y↑"
    assert short_label("Z (Up)") == "Z↑"
    assert short_label("-Y") == "-Y"


def test_ue_and_maya_up_marker_lands_on_different_local_axes():
    """端到端锁点:Maya 下 Up 标记在局部 Y 上,切到 UE 后必须挪到局部 Z 上,
    以此覆盖"颜色/方向已变而字母未变"时 Up 标记不能丢失的链路。
    """
    vr = view_rotation_from_matrix(_IDENTITY_M16)
    maya_labels = [short_label(a.label) for a in project_axes(vr, CONVENTIONS["maya"])]
    ue_labels = [short_label(a.label) for a in project_axes(vr, CONVENTIONS["ue"])]
    assert maya_labels == ["X", "Y↑", "Z"]
    assert ue_labels == ["X", "Z↑", "Y"]
