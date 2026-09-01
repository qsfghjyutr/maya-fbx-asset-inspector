"""用户检查预设模板 —— 复制本文件、改名后编辑。

本文件以下划线开头，因此插件加载器会跳过它。复制为不以下划线开头的文件后，
其中登记的 Profile 会自动出现在检查器的“检查预设”下拉框中。

下面的规则显式示范检查 colorSet1 的 RGBA 范围，并为每个分量生成一套灰度可视化。
内置“默认”预设不会强制任何通道值域；请按项目语义配置或移除这里的校验器。
"""

from __future__ import annotations

from fbx_inspector.core.channel import Channel, SourceType
from fbx_inspector.core.registry import register_profile
from fbx_inspector.decode.builtin import ScalarFromComponent
from fbx_inspector.rules.profile import Profile, Rule
from fbx_inspector.rules.preflight import UVSetCountCheck
from fbx_inspector.validate.builtin import RangeCheck
from fbx_inspector.visualize.colorset import ColorSetRemapVisualizer


def _build_profile() -> Profile:
    rules = []
    for component in ("R", "G", "B", "A"):
        rules.append(
            Rule(
                id=f"my_studio_colorSet1_{component}",
                decoder=ScalarFromComponent(component=component),
                channel_roles={"in": Channel(SourceType.COLOR_SET, "colorSet1")},
                visualizer=ColorSetRemapVisualizer(
                    ramp="grayscale",
                    normalize=False,
                    set_suffix=f"my_studio_{component}",
                ),
                validators=[RangeCheck(0.0, 1.0)],
            )
        )
    return Profile(
        id="my_studio:default",
        name="我的工作室预设",
        description="检查 colorSet1 的 R/G/B/A 范围，并生成四套灰度可视化。",
        rules=rules,
        match_pattern=None,
        # 未配置分级规则时，该要求会自动检查全部 LOD。
        preflight_checks=[UVSetCountCheck(expected=2)],
        # 如各 LOD 要求不同，可按检查 id 覆盖默认要求：
        # lod_preflight_checks={1: [UVSetCountCheck(expected=1)]},
    )


register_profile(_build_profile(), overwrite=True)
