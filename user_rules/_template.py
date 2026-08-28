"""用户规则模板 —— 复制本文件、改名后编辑。

⚠️ 本文件以下划线开头,会被插件加载器**跳过**。请复制成不以下划线开头的新文件
   (如 ``my_rules.py``)再编辑,否则不会被加载。

下面演示三种常见定制:自定义解码器、自定义校验器、以及登记一个配置档。
"""

from __future__ import annotations

from fbx_inspector.core.channel import Channel, ChannelData, SourceType
from fbx_inspector.core.registry import decoder, register_profile, validator
from fbx_inspector.core.types import DataKind, DecodedData, Issue, Severity
from fbx_inspector.decode.base import Decoder
from fbx_inspector.rules.profile import Profile, Rule
from fbx_inspector.validate.base import Validator
from fbx_inspector.visualize.colorset import ColorSetRemapVisualizer


@decoder("my_scalar")  # 登记 id,便于复用/查找
class MyScalarDecoder(Decoder):
    """示例:把某个 UV 分量当标量读出(把解包/换算逻辑写在这里)。"""

    roles = ("in",)
    output_kind = DataKind.SCALAR

    def __init__(self, component: str = "U") -> None:
        self.component = component

    def decode(self, channels: dict[str, ChannelData]) -> DecodedData:
        self._require(channels)
        cd = channels["in"]
        col = cd.component(self.component)
        # 在此按具体编码做换算,这里仅原样透传
        return DecodedData(
            kind=DataKind.SCALAR,
            values=[(v,) for v in col],
            vertex_ids=list(cd.vertex_ids),
            face_ids=list(cd.face_ids),
            label=f"{cd.channel}.{self.component}",
        )


@validator("my_positive")
class MyPositiveCheck(Validator):
    """示例:要求所有值 > 0。"""

    def validate(self, data: DecodedData) -> list[Issue]:
        issues: list[Issue] = []
        for i, val in enumerate(data.values):
            if any(c <= 0.0 for c in val):
                issues.append(
                    Issue(
                        severity=Severity.WARNING,
                        message=f"存在非正值 {val}",
                        face_id=data.face_ids[i],
                        vertex_id=data.vertex_ids[i],
                        value=val,
                    )
                )
        return issues


def _build_profile() -> Profile:
    return Profile(
        id="my_studio:example",
        match_pattern=r"^prop_",  # 只对名字以 prop_ 开头的资产生效;None 表示不限
        rules=[
            Rule(
                id="my_uv_check",
                decoder=MyScalarDecoder(component="U"),
                channel_roles={"in": Channel(SourceType.UV_SET, "uvSet2")},
                visualizer=ColorSetRemapVisualizer(ramp="grayscale"),
                validators=[MyPositiveCheck()],
            )
        ],
    )


# 导入本模块时即登记配置档,使 plugins.discover() 能发现它。
register_profile(_build_profile(), overwrite=True)
