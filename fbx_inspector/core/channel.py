"""通道抽象(与 Maya 无关)。

`Channel` 描述"从哪里取原始数据"——某个 color set 或某个 UV set;
`ChannelData` 是从网格读出的、按面顶点顺序排列的原始分量数组。
真正的读取发生在 `core.mesh_data`(仅 Maya),这里只定义与 DCC 无关的形状。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourceType(Enum):
    """通道来源类型。"""

    COLOR_SET = "colorSet"
    UV_SET = "uvSet"


# 各来源类型天然拥有的分量名。color set 即使表示为 RGB,也统一按 RGBA 读取,
# 缺失的 A 由读取层补 1.0,以简化下游解码器。
COMPONENTS: dict[SourceType, tuple[str, ...]] = {
    SourceType.COLOR_SET: ("R", "G", "B", "A"),
    SourceType.UV_SET: ("U", "V"),
}


@dataclass(frozen=True)
class Channel:
    """一个数据源的稳定标识:来源类型 + 集合名。

    不含分量选择——挑哪个分量(R / U / ……)是解码器的职责。
    """

    source: SourceType
    name: str

    @property
    def components(self) -> tuple[str, ...]:
        return COMPONENTS[self.source]

    def __str__(self) -> str:  # 便于日志与报告
        return f"{self.source.value}:{self.name}"


@dataclass
class ChannelData:
    """从网格按面顶点顺序读出的原始数据。

    ``components`` 的每个数组、``vertex_ids``、``face_ids`` 长度一致且逐元素对齐。
    """

    channel: Channel
    components: dict[str, list[float]] = field(default_factory=dict)
    vertex_ids: list[int] = field(default_factory=list)
    face_ids: list[int] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.vertex_ids)

    def component(self, name: str) -> list[float]:
        """取某个分量数组;分量名不属于该来源类型时报错。"""
        if name not in self.channel.components:
            raise KeyError(
                f"通道 {self.channel} 没有分量 {name!r};可用:{self.channel.components}"
            )
        return self.components[name]
