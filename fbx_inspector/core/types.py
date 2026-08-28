"""解码后数据的类型定义(与 Maya 无关)。

`DecodedData` 是解码器的统一输出:一串与"面顶点遍历顺序"逐元素对齐的值,
每个值旁都带着来源的 `face_id` 与 `vertex_id`,以便校验器精确定位、
可视化器精确写回。详见 DESIGN.md 中关于逐面顶点数据模型的说明。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class DataKind(Enum):
    """解码结果的语义类型。每个 `values` 元素的分量个数由它决定。"""

    SCALAR = "scalar"  # 1 个分量
    VEC2 = "vec2"      # 2 个分量
    VEC3 = "vec3"      # 3 个分量
    VEC4 = "vec4"      # 4 个分量
    MASK = "mask"      # 1 个分量,取值语义为布尔/开关
    ENUM = "enum"      # 1 个分量,取值语义为离散枚举下标

    @property
    def arity(self) -> int:
        """该类型下每个值应有的分量个数。"""
        return {
            DataKind.SCALAR: 1,
            DataKind.VEC2: 2,
            DataKind.VEC3: 3,
            DataKind.VEC4: 4,
            DataKind.MASK: 1,
            DataKind.ENUM: 1,
        }[self]


@dataclass
class DecodedData:
    """一次解码的完整结果。

    约定:``len(values) == len(vertex_ids) == len(face_ids)``,且三者逐元素对齐;
    每个 ``values[i]`` 是一个长度等于 ``kind.arity`` 的浮点元组。
    """

    kind: DataKind
    values: Sequence[tuple[float, ...]]
    vertex_ids: Sequence[int]
    face_ids: Sequence[int]
    label: str = ""  # 人类可读标签,用于 UI / 报告,例如 "AO (uvSet2.U)"

    def __post_init__(self) -> None:
        n = len(self.values)
        if not (len(self.vertex_ids) == len(self.face_ids) == n):
            raise ValueError(
                "values / vertex_ids / face_ids 长度必须一致:"
                f"{n} / {len(self.vertex_ids)} / {len(self.face_ids)}"
            )
        arity = self.kind.arity
        # 只抽查第一个元素的分量数,避免逐元素校验拖慢大网格。
        if n and len(self.values[0]) != arity:
            raise ValueError(
                f"{self.kind.name} 期望每个值有 {arity} 个分量,实际得到 {len(self.values[0])}"
            )

    def __len__(self) -> int:
        return len(self.values)


@dataclass
class Issue:
    """一条校验发现的问题,可精确定位到某个面顶点。"""

    severity: "Severity"
    message: str
    face_id: int = -1     # -1 表示"非组件级"的整体性问题
    vertex_id: int = -1
    value: tuple[float, ...] | None = None


class Severity(Enum):
    """问题的严重级别。"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class VisualizeInfo:
    """可视化施加后回传给报告的信息(与 Maya 无关)。

    目前用于展示归一化所依据的**当前通道数据区间**:``normalize=True`` 时值被
    线性映射到 [data_min, data_max] → [0,1],随报告展示该区间以说明颜色的归一化依据;
    ``normalized=False`` 时区间仅供参考(实际按原始值裁剪到 [0,1])。
    """

    normalized: bool = False
    data_min: float | None = None
    data_max: float | None = None


@dataclass
class RuleResult:
    """单条规则运行后的结果:校验问题 + 可视化是否已应用。"""

    rule_id: str
    issues: list[Issue] = field(default_factory=list)
    visualized: bool = False
    label: str = ""
    #: 可视化回传信息(如归一化区间);未可视化时为 None。
    viz_info: "VisualizeInfo | None" = None

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity is Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity is Severity.WARNING)
