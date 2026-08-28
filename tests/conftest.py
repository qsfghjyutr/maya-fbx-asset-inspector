"""共享测试夹具:无需 Maya 的假网格。"""

from __future__ import annotations

from fbx_inspector.core.channel import Channel, ChannelData, SourceType


class FakeMesh:
    """实现 rules.MeshLike 的鸭子类型:按预置数据返回 ChannelData。

    ``channels`` 形如 {Channel: {"R":[...], ...}},并共享同一组 vertex/face id。
    """

    def __init__(self, channels: dict[Channel, dict[str, list[float]]],
                 vertex_ids: list[int], face_ids: list[int]) -> None:
        self._channels = channels
        self._vids = vertex_ids
        self._fids = face_ids

    def read_channel(self, channel: Channel) -> ChannelData:
        comps = self._channels[channel]
        return ChannelData(
            channel=channel,
            components={k: list(v) for k, v in comps.items()},
            vertex_ids=list(self._vids),
            face_ids=list(self._fids),
        )


def make_uv_mesh(u_values: list[float]) -> tuple[FakeMesh, Channel]:
    """构造一个只有 uvSet2 的假网格,U 存给定标量,V 全 0。"""
    chan = Channel(SourceType.UV_SET, "uvSet2")
    n = len(u_values)
    mesh = FakeMesh(
        channels={chan: {"U": list(u_values), "V": [0.0] * n}},
        vertex_ids=list(range(n)),
        face_ids=[i // 3 for i in range(n)],
    )
    return mesh, chan
