"""解码器单测(无需 Maya)。"""

from __future__ import annotations

from fbx_inspector.core.channel import Channel, ChannelData, SourceType
from fbx_inspector.core.coord_convention import CONVENTIONS, flip_uv_v
from fbx_inspector.core.types import DataKind
from fbx_inspector.decode.builtin import (
    ScalarFromComponent,
    UnpackTwo8Bit,
    Vec3FromRGB,
)


def _color_channel(r, g, b, a=None):
    n = len(r)
    chan = Channel(SourceType.COLOR_SET, "colorSet1")
    comps = {"R": list(r), "G": list(g), "B": list(b), "A": list(a or [1.0] * n)}
    return ChannelData(chan, comps, list(range(n)), [0] * n)


def test_scalar_from_component_picks_u():
    chan = Channel(SourceType.UV_SET, "uvSet2")
    cd = ChannelData(chan, {"U": [0.1, 0.9], "V": [0.0, 0.0]}, [0, 1], [0, 0])
    out = ScalarFromComponent(component="U").decode({"in": cd})
    assert out.kind is DataKind.SCALAR
    assert out.values == [(0.1,), (0.9,)]
    assert out.vertex_ids == [0, 1]


def test_vec3_from_rgb_signed_remap():
    cd = _color_channel([0.5, 1.0], [0.5, 0.0], [0.5, 1.0])
    out = Vec3FromRGB(remap_signed=True).decode({"in": cd})
    assert out.kind is DataKind.VEC3
    # 0.5 -> 0.0, 1.0 -> 1.0, 0.0 -> -1.0
    assert out.values[0] == (0.0, 0.0, 0.0)
    assert out.values[1] == (1.0, -1.0, 1.0)


def test_unpack_two_8bit_roundtrip():
    # 打包 hi=200, lo=50 -> (200<<8 | 50)/65535
    packed = ((200 << 8) | 50) / 65535.0
    cd = _color_channel([packed], [0.0], [0.0])
    out = UnpackTwo8Bit(component="R").decode({"in": cd})
    hi, lo = out.values[0]
    assert round(hi * 255) == 200
    assert round(lo * 255) == 50


def test_scalar_from_component_sees_flipped_v_under_ue():
    # 解码前先按 UE 约定翻 V,解码器应看到翻转后的值(忠实复现 UE"先翻 V 再解码")。
    # 0.25/0.75 精确可表示,1-v 不会有舍入误差。
    chan = Channel(SourceType.UV_SET, "uvSet2")
    cd = ChannelData(chan, {"U": [0.1, 0.9], "V": [0.25, 0.75]}, [0, 1], [0, 0])
    channels = {"in": cd}
    flip_uv_v(channels, CONVENTIONS["ue"], enabled=True)

    v_out = ScalarFromComponent(component="V").decode(channels)
    assert v_out.values == [(0.75,), (0.25,)]

    u_out = ScalarFromComponent(component="U").decode(channels)
    assert u_out.values == [(0.1,), (0.9,)]  # U 不受 V 翻转影响
