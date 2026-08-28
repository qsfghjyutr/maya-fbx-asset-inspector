"""Rule / Profile —— 定制的核心单位(与 Maya 无关)。

Rule 把一组具体 Channel 绑定到解码器的角色名,再配上可选可视化器与若干校验器。
Profile 是一组带可选资产名匹配器的 Rule 集合,方便工作室整体交付一套规范。

运行 Rule 需要一个能读通道、并接受可视化写入的 mesh 对象——即 Maya 内的
`core.mesh_data.MeshData`。为保持本模块可测试,这里只依赖它的鸭子类型:
需要 ``read_channel(channel)`` 方法。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from ..core.channel import Channel, ChannelData
from ..core.context import InspectionContext
from ..core.types import RuleResult
from ..decode.base import Decoder
from ..validate.base import Validator
from ..visualize.base import Visualizer


class MeshLike(Protocol):
    """Rule 运行所需的最小 mesh 接口(便于用假对象做单测)。"""

    def read_channel(self, channel: Channel) -> ChannelData: ...


@dataclass
class Rule:
    """一条检查规则。"""

    id: str
    decoder: Decoder
    #: 解码器角色名 → 具体通道。键须覆盖 decoder.roles。
    channel_roles: dict[str, Channel] = field(default_factory=dict)
    visualizer: Visualizer | None = None
    validators: list[Validator] = field(default_factory=list)

    def run(self, mesh: MeshLike, ctx: InspectionContext) -> RuleResult:
        """读取通道 → 解码 → (校验) → (可视化),汇总成 RuleResult。"""
        channels = {
            role: mesh.read_channel(chan) for role, chan in self.channel_roles.items()
        }
        data = self.decoder.decode(channels)

        result = RuleResult(rule_id=self.id, label=data.label)
        for v in self.validators:
            result.issues.extend(v.validate(data))

        if self.visualizer is not None and not ctx.validate_only:
            if not self.visualizer.can_handle(data.kind):
                raise TypeError(
                    f"规则 {self.id} 的可视化器不接受 {data.kind.name} 数据"
                )
            result.viz_info = self.visualizer.apply(mesh, data, ctx)
            result.visualized = True

        return result


@dataclass
class Profile:
    """一组规则,带可选的资产名匹配(正则)。"""

    id: str
    rules: list[Rule] = field(default_factory=list)
    #: 资产名匹配正则;None 表示适用于任何资产。
    match_pattern: str | None = None

    def matches(self, asset_name: str) -> bool:
        if self.match_pattern is None:
            return True
        return re.search(self.match_pattern, asset_name) is not None

    def run(self, mesh: MeshLike, ctx: InspectionContext) -> list[RuleResult]:
        return [rule.run(mesh, ctx) for rule in self.rules]
