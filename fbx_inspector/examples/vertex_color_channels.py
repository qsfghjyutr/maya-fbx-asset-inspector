"""示例:分通道可视化顶点色(开箱即用)。

顶点色的 R/G/B/A 常各存一路数据,混合显示时难以分辨每一路的内容。本示例为每个分量单独
生成一个热力图 color set,可逐路查看;并演示用 chramp 式的 `Ramp` 曲线对 0-1 数据做
二次映射来增强可读性。

用法(Maya 内,已选中网格):

    import maya.cmds as cmds
    from fbx_inspector.api import run_profile, clear_visualizations
    from fbx_inspector.examples.vertex_color_channels import vertex_color_channels_profile

    mesh = cmds.ls(selection=True)[0]
    profile = vertex_color_channels_profile("colorSet1")   # 替换为目标 color set 名
    run_profile(mesh, profile)
    # 之后在网格属性里切换 current color set,即可逐路查看 __inspector___R/_G/_B/_A
    # clear_visualizations(mesh, profile)   # 查看完毕后清理

要给某一路叠加二次曲线增强对比:

    from fbx_inspector.core.remap import Ramp
    rule = channel_view_rule("colorSet1", "R", curve=Ramp.quadratic())
"""

from __future__ import annotations

from ..core.channel import Channel, SourceType
from ..core.registry import register_profile
from ..core.remap import Ramp
from ..decode.builtin import ScalarFromComponent
from ..rules.profile import Profile, Rule
from ..validate.builtin import RangeCheck
from ..visualize.colorset import ColorSetRemapVisualizer

CHANNELS = ("R", "G", "B", "A")


def channel_view_rule(
    color_set: str,
    component: str,
    *,
    ramp: str = "grayscale",
    curve: Ramp | None = None,
    normalize: bool = False,
    check_range: bool = False,
) -> Rule:
    """构造"查看某个 color set 的某个分量"的规则。

    每条规则写入名为 ``{prefix}_{component}`` 的独立 color set,互不覆盖。
    ``normalize=False`` 忠实显示原始 0-1;``curve`` 可叠加 Ramp 塑形;
    默认不限制值域；``check_range=True`` 时附带 [0,1] 范围校验。
    """
    if component not in CHANNELS:
        raise ValueError(f"分量须为 {CHANNELS} 之一,收到 {component!r}")
    suffix = component if curve is None else f"{component}_curved"
    return Rule(
        id=f"view_{color_set}_{suffix}",
        decoder=ScalarFromComponent(component=component),
        channel_roles={"in": Channel(SourceType.COLOR_SET, color_set)},
        visualizer=ColorSetRemapVisualizer(
            ramp=ramp, normalize=normalize, curve=curve, set_suffix=suffix
        ),
        validators=[RangeCheck(0.0, 1.0)] if check_range else [],
    )


def vertex_color_channels_profile(
    color_set: str = "colorSet1",
    *,
    ramp: str = "grayscale",
    channels: tuple[str, ...] = CHANNELS,
) -> Profile:
    """为一个 color set 的各分量各生成一条查看规则,打包成配置档。"""
    return Profile(
        id=f"vertex_color_channels:{color_set}",
        rules=[channel_view_rule(color_set, c, ramp=ramp) for c in channels],
    )


# —— 登记两个可被发现的示例配置档(绑定到常见的默认名 colorSet1)——
register_profile(vertex_color_channels_profile("colorSet1"), overwrite=True)
register_profile(
    Profile(
        id="vertex_color_channels:colorSet1:quadratic",
        rules=[
            channel_view_rule("colorSet1", c, curve=Ramp.quadratic()) for c in CHANNELS
        ],
    ),
    overwrite=True,
)
