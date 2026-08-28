"""core/coord_convention.py 的单测(无需 Maya)。"""

from __future__ import annotations

from fbx_inspector.core.channel import Channel, ChannelData, SourceType
from fbx_inspector.core.coord_convention import (
    CONVENTIONS,
    IDENTITY,
    apply3x3,
    axis_label_map,
    determinant3x3,
    flip_uv_v,
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


def _uv_channel_data(u, v):
    chan = Channel(SourceType.UV_SET, "uvSet2")
    n = len(v)
    return ChannelData(chan, {"U": list(u), "V": list(v)}, list(range(n)), [0] * n)


def _color_channel_data(r):
    chan = Channel(SourceType.COLOR_SET, "colorSet1")
    n = len(r)
    return ChannelData(
        chan, {"R": list(r), "G": [0.0] * n, "B": [0.0] * n, "A": [1.0] * n},
        list(range(n)), [0] * n,
    )


def test_convention_flip_uv_v_flags():
    assert CONVENTIONS["maya"].flip_uv_v is False
    assert CONVENTIONS["ue"].flip_uv_v is True


def test_flip_uv_v_flips_v_only_for_ue_when_enabled():
    # 0.25/0.75/0.0/1.0 在二进制浮点下精确可表示,1-v 不会有舍入误差。
    cd = _uv_channel_data([0.1, 0.9], [0.25, 0.75])
    channels = {"in": cd}
    out = flip_uv_v(channels, CONVENTIONS["ue"], enabled=True)
    assert out is channels  # 原地修改并返回同一 dict,便于链式调用
    assert cd.components["V"] == [0.75, 0.25]
    assert cd.components["U"] == [0.1, 0.9]  # U 不受影响
    assert cd.vertex_ids == [0, 1]  # 长度与对齐关系不变


def test_flip_uv_v_noop_for_maya_convention():
    cd = _uv_channel_data([0.1, 0.9], [0.25, 0.75])
    flip_uv_v({"in": cd}, CONVENTIONS["maya"], enabled=True)
    assert cd.components["V"] == [0.25, 0.75]


def test_flip_uv_v_noop_when_disabled():
    cd = _uv_channel_data([0.1, 0.9], [0.25, 0.75])
    flip_uv_v({"in": cd}, CONVENTIONS["ue"], enabled=False)
    assert cd.components["V"] == [0.25, 0.75]


def test_flip_uv_v_does_not_touch_color_set_channels():
    cd = _color_channel_data([0.25, 0.75])
    flip_uv_v({"in": cd}, CONVENTIONS["ue"], enabled=True)
    assert cd.components["R"] == [0.25, 0.75]
