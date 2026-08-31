"""开箱即用的默认检查预设，也是 user_rules/_template.py 的基准配置。"""

from __future__ import annotations

from ..core.channel import Channel, SourceType
from ..core.registry import register_profile
from ..decode.builtin import ScalarFromComponent
from ..rules.profile import Profile, Rule
from ..validate.builtin import RangeCheck
from ..visualize.colorset import ColorSetRemapVisualizer

DEFAULT_PROFILE_ID = "default"


def default_profile() -> Profile:
    """检查 colorSet1 的 RGBA，并为每个分量生成独立灰度可视化。"""
    rules = []
    for component in ("R", "G", "B", "A"):
        rules.append(
            Rule(
                id=f"default_colorSet1_{component}",
                decoder=ScalarFromComponent(component=component),
                channel_roles={"in": Channel(SourceType.COLOR_SET, "colorSet1")},
                visualizer=ColorSetRemapVisualizer(
                    ramp="grayscale",
                    normalize=False,
                    set_suffix=f"default_{component}",
                ),
                validators=[RangeCheck(0.0, 1.0)],
            )
        )
    return Profile(
        id=DEFAULT_PROFILE_ID,
        name="默认",
        description="检查 colorSet1 的 R/G/B/A 范围，并生成四套灰度可视化。",
        rules=rules,
    )


register_profile(default_profile(), overwrite=True)

__all__ = ["DEFAULT_PROFILE_ID", "default_profile"]
