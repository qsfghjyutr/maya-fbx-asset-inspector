"""内置解码器(与 Maya 无关)。

这些是可直接使用、也可作为编写自定义解码器范例的基础实现。
每个都用 `@decoder("id")` 登记到全局注册表。
"""

from __future__ import annotations

from ..core.channel import ChannelData
from ..core.registry import decoder
from ..core.types import DataKind, DecodedData
from .base import Decoder


@decoder("scalar_from_component")
class ScalarFromComponent(Decoder):
    """从单个分量抽取标量,例如 "UV2 的 U 存的是 AO"。"""

    roles = ("in",)
    output_kind = DataKind.SCALAR

    def __init__(self, component: str = "R") -> None:
        self.component = component

    def decode(self, channels: dict[str, ChannelData]) -> DecodedData:
        self._require(channels)
        cd = channels["in"]
        col = cd.component(self.component)
        return DecodedData(
            kind=DataKind.SCALAR,
            values=[(v,) for v in col],
            vertex_ids=list(cd.vertex_ids),
            face_ids=list(cd.face_ids),
            label=f"{cd.channel}.{self.component}",
        )


@decoder("vec3_from_rgb")
class Vec3FromRGB(Decoder):
    """把 color set 的 RGB 解释成一个三维向量,例如切线空间法线。

    ``remap_signed=True`` 时按 ``v*2-1`` 把 [0,1] 还原为 [-1,1]。
    """

    roles = ("in",)
    output_kind = DataKind.VEC3

    def __init__(self, remap_signed: bool = False) -> None:
        self.remap_signed = remap_signed

    def decode(self, channels: dict[str, ChannelData]) -> DecodedData:
        self._require(channels)
        cd = channels["in"]
        r, g, b = cd.component("R"), cd.component("G"), cd.component("B")

        def m(x: float) -> float:
            return x * 2.0 - 1.0 if self.remap_signed else x

        return DecodedData(
            kind=DataKind.VEC3,
            values=[(m(r[i]), m(g[i]), m(b[i])) for i in range(len(cd))],
            vertex_ids=list(cd.vertex_ids),
            face_ids=list(cd.face_ids),
            label=f"{cd.channel}.RGB",
        )


@decoder("unpack_two_8bit")
class UnpackTwo8Bit(Decoder):
    """把单个分量里打包的两个 8-bit 值拆成 vec2。

    约定原始值 ∈ [0,1],代表一个 16-bit 定点数:高 8 位、低 8 位。
    这是游戏资产里常见的打包手法,单独列出作为"解包住在解码器里"的范例。
    """

    roles = ("in",)
    output_kind = DataKind.VEC2

    def __init__(self, component: str = "R") -> None:
        self.component = component

    def decode(self, channels: dict[str, ChannelData]) -> DecodedData:
        self._require(channels)
        cd = channels["in"]
        col = cd.component(self.component)
        out: list[tuple[float, float]] = []
        for v in col:
            packed = round(max(0.0, min(1.0, v)) * 65535.0)
            hi = (packed >> 8) & 0xFF
            lo = packed & 0xFF
            out.append((hi / 255.0, lo / 255.0))
        return DecodedData(
            kind=DataKind.VEC2,
            values=out,
            vertex_ids=list(cd.vertex_ids),
            face_ids=list(cd.face_ids),
            label=f"{cd.channel}.{self.component} (unpacked 8+8)",
        )
