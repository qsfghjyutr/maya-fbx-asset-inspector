"""通道 → 规则 的工厂(与 Maya 无关)。

把"某个 color set / UV set 的某个分量"落成一条标量查看规则,供检查窗口与单测共用。
窗口每选一个通道就用它现造一条 Rule:解码器取该分量、可视化器按当前色带/曲线着色、
再附带范围校验。可视化器的写入目标(场景网格 vs 窗口里的副本)由调用方决定——窗口会把它
apply 到隔离面板中的临时副本上。
"""

from __future__ import annotations

from ..core.channel import Channel, SourceType
from ..core.remap import Ramp
from ..decode.builtin import ScalarFromComponent
from ..rules.profile import Rule
from ..validate.builtin import RangeCheck
from ..visualize.colorset import ColorSetRemapVisualizer


def scalar_rule_for(
    source: SourceType,
    set_name: str,
    component: str,
    *,
    ramp: str = "grayscale",
    curve: Ramp | None = None,
    normalize: bool = True,
    check_range: bool = True,
    set_suffix: str = "view",
) -> Rule:
    """构造"查看 ``set_name`` 的 ``component`` 分量"的标量规则。

    ``component`` 须是该来源类型的合法分量(color set 为 R/G/B/A,UV set 为 U/V)。
    ``set_suffix`` 决定写入哪个显示 color set;窗口用固定后缀,使切换通道时复用同一个
    显示集(一次只看一路)。
    """
    channel = Channel(source, set_name)
    if component not in channel.components:
        raise ValueError(
            f"{source.value} 的合法分量为 {channel.components},收到 {component!r}"
        )
    return Rule(
        id=f"view:{channel}.{component}",
        decoder=ScalarFromComponent(component=component),
        channel_roles={"in": channel},
        visualizer=ColorSetRemapVisualizer(
            ramp=ramp, normalize=normalize, curve=curve, set_suffix=set_suffix
        ),
        validators=[RangeCheck(0.0, 1.0)] if check_range else [],
    )
