"""core/coord_convention.py 的单测(无需 Maya)。"""

from __future__ import annotations

from fbx_inspector.core.coord_convention import (
    CONVENTIONS,
    IDENTITY,
    apply3x3,
    axis_label_map,
    determinant3x3,
    to_maya_matrix44,
)


def test_maya_is_identity_and_right_handed():
    maya = CONVENTIONS["maya"]
    assert maya.matrix == IDENTITY
    assert determinant3x3(maya.matrix) == 1.0
    assert maya.is_mirror is False
    assert maya.apply((1.0, 2.0, 3.0)) == (1.0, 2.0, 3.0)


def test_ue_swaps_up_axis_and_flips_handedness():
    ue = CONVENTIONS["ue"]
    # Maya 的上方向 Y 变换到 UE 的上方向 Z。
    assert ue.apply((0.0, 1.0, 0.0)) == (0.0, 0.0, 1.0)
    # Maya 的 Z 变换到 Y。
    assert ue.apply((0.0, 0.0, 1.0)) == (0.0, 1.0, 0.0)
    # X 不变。
    assert ue.apply((1.0, 0.0, 0.0)) == (1.0, 0.0, 0.0)
    # 换手性:行列式为负,is_mirror 为真。
    assert determinant3x3(ue.matrix) == -1.0
    assert ue.is_mirror is True


def test_apply3x3_matches_manual_dot():
    m = ((2.0, 0.0, 0.0), (0.0, 3.0, 0.0), (0.0, 0.0, 4.0))
    assert apply3x3(m, (1.0, 1.0, 1.0)) == (2.0, 3.0, 4.0)


def test_axis_label_map_marks_up_axis():
    labels = axis_label_map(CONVENTIONS["ue"])
    # Maya 局部 Y(下标 1)在 UE 约定下落到 up 轴 Z 上。
    assert "Z" in labels[1]
    assert "Up" in labels[1]
    # Maya 局部 X(下标 0)仍是 X,且不是 up。
    assert labels[0] == "X"


def test_maya_labels_are_self_consistent():
    labels = axis_label_map(CONVENTIONS["maya"])
    assert labels[0] == "X"
    assert labels[1] == "Y (Up)"
    assert labels[2] == "Z"


def test_to_maya_matrix44_identity_and_ue():
    # 恒等 3x3 → Maya 4x4 单位矩阵。
    assert to_maya_matrix44(IDENTITY) == [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    # UE 矩阵按列主序摆放:平移块为 0,右下角为 1。
    ue44 = to_maya_matrix44(CONVENTIONS["ue"].matrix)
    assert len(ue44) == 16
    assert ue44[12:] == [0.0, 0.0, 0.0, 1.0]  # 平移列 + 齐次位
