"""解码器抽象基类(与 Maya 无关)。

解码器把一组具名的"角色 → ChannelData"映射,解释成有类型的 `DecodedData`。
角色名让规则得以把任意通道插到解码器的输入上(见 rules/profile.py)。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..core.channel import ChannelData
from ..core.types import DataKind, DecodedData


class Decoder(ABC):
    """所有解码器的基类。"""

    #: 该解码器需要的输入角色名。规则必须为每个角色绑定一个 Channel。
    roles: tuple[str, ...] = ("in",)

    #: 输出的数据类型。
    output_kind: DataKind = DataKind.SCALAR

    @abstractmethod
    def decode(self, channels: dict[str, ChannelData]) -> DecodedData:
        """执行解码。``channels`` 的键须覆盖 ``self.roles``。"""
        raise NotImplementedError

    # —— 供子类复用的小工具 ——
    def _require(self, channels: dict[str, ChannelData]) -> None:
        missing = [r for r in self.roles if r not in channels]
        if missing:
            raise KeyError(f"{type(self).__name__} 缺少角色通道:{missing}")
