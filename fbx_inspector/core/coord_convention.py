"""坐标约定(与 Maya 无关)。

维护"Maya 局部空间 → 目标引擎坐标约定"的数据变换,并派生目标引擎坐标轴在 Maya modelPanel
中的显示基。预览模型本身不换轴;坐标矩阵只负责轴方向和数值解释。Maya 是 **Y-up、右手系**;不同
引擎的 up 轴 / 手性不同,这里的 ``matrix`` 是相对 Maya 局部空间的 3x3 线性变换——单位矩阵表示
"跟 Maya 一致,不变换"。

⚠️ Maya → Unreal Engine 的默认换算(X 不变、Y↔Z 互换,即 up 轴从 Y 换到 Z)。这不是随手取的
"业界惯例",而是**已对照 UE 5.8 源码逐行核实**的导入器净变换(默认走 Interchange 的 FBX-SDK
后端,``bUseUfbxParser`` 默认 false):UE 先用 ``FbxAxisSystem::ConvertScene`` 把场景转到
Z-up / front=-Y 的右手系(纯旋转,det +1),再用 ``FFbxConvert::ConvertPos`` 取反 Y(det -1),
两步合成正好等于 X 不变、Y↔Z 互换,det = -1。位置与法线/切线走**同一个**变换。源码见
``Engine/Plugins/Interchange/.../Parsers/Fbx/Private/FbxConvert.{h,cpp}`` 与 ``FbxMesh.cpp``。

UV ``V→1-V`` 也是 UE 导入器会做的事,但它不是 3D 线性变换(UV 是 2D,且 1-V 含平移),故**不进
``matrix``**,而由 ``CoordConvention.flip_uv_v`` 布尔标志声明、``flip_uv_v()`` 纯函数在解码前作用于
UV 通道的 V 分量(见下)。其余 UE 也会做、但因不影响副本朝向而与本模块无关的事:单位缩放到 cm、
binormal 额外取一次反。项目若开 ``bForceFrontXAxis``(front=+X、关节额外
``Rot(-90,-90,0)``),净变换会不同——届时只需改 ``CONVENTIONS`` 这一处常量,不影响其余代码。

关键的正确性提示:Maya(右手)→ UE(左手)是**换手性**(矩阵行列式为负,即镜像),不是纯旋转——
纯旋转的行列式恒为 +1,做不出手性翻转。``CoordConvention.is_mirror`` 描述数据换轴是否镜像;
预览不把该矩阵作用到模型,否则还需乘逆显示基并必然抵消,属于冗余操作。
"""

from __future__ import annotations

from dataclasses import dataclass

from .channel import ChannelData, SourceType

Matrix3 = tuple[
    tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]
]
Vector3 = tuple[float, float, float]

IDENTITY: Matrix3 = (
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)

# Maya(Y-up,右手)→ UE(Z-up,左手):X 不变,Maya 的 Y(up)搬到 Z,Maya 的 Z 搬到 Y。
# 行列式为 -1 —— 换手性(镜像),不是单纯旋转。此矩阵 = UE 5.8 导入器对 Y-up RH FBX 的净变换
#(ConvertScene 旋转 ∘ 取反 Y),已对照源码核实;位置与法线共用同一个变换。
MAYA_TO_UE: Matrix3 = (
    (1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, 1.0, 0.0),
)

_AXIS_NAMES = ("X", "Y", "Z")


def apply3x3(m: Matrix3, v: Vector3) -> Vector3:
    """把 3x3 矩阵作用在一个向量上(逐行点乘)。"""
    return tuple(sum(row[i] * v[i] for i in range(3)) for row in m)  # type: ignore[return-value]


def determinant3x3(m: Matrix3) -> float:
    (a, b, c), (d, e, f), (g, h, i) = m
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def inverse3x3(m: Matrix3) -> Matrix3:
    """返回非奇异 3x3 坐标基矩阵的逆矩阵。"""
    (a, b, c), (d, e, f), (g, h, i) = m
    det = determinant3x3(m)
    if abs(det) < 1e-12:
        raise ValueError("coordinate convention matrix must be invertible")
    return (
        ((e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det),
        ((f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det),
        ((d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det),
    )


def to_maya_matrix44(m: Matrix3) -> list[float]:
    """把 3x3 线性变换摆进 Maya 的 4x4(``cmds.xform`` 用的列主序 16 元组,平移为 0)。

    抽出来是为了让 ``ui/viewport_panel.py`` 和无头冒烟测试共用同一份构造,不各写一遍。
    """
    return [
        m[0][0], m[1][0], m[2][0], 0.0,
        m[0][1], m[1][1], m[2][1], 0.0,
        m[0][2], m[1][2], m[2][2], 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


def view_rotation_from_matrix(m16: list[float]) -> Matrix3:
    """从 Maya 相机世界矩阵(``cmds.xform ... matrix`` 的 16 元组)取"世界→相机"旋转 3x3。

    Maya 世界矩阵是行主序、行向量约定(``p_world = p_local · M``),其前三行的前三列即相机
    局部 X/Y/Z 轴在世界里的方向。把它们作为 3x3 的三行,``apply3x3(view_rot, v_world)`` 就是把
    世界向量点乘到相机局部系(= 投影到屏幕)所需的运算。抽成纯函数以便脱离 Maya 单测。
    """
    return (
        (m16[0], m16[1], m16[2]),
        (m16[4], m16[5], m16[6]),
        (m16[8], m16[9], m16[10]),
    )


@dataclass(frozen=True)
class CoordConvention:
    """一套坐标约定:Maya 局部空间到该约定下的变换 + 展示信息。"""

    id: str
    label: str  # 显示名,如 "Unreal Engine（Z-up，左手）"
    up_axis: str  # 该约定下的世界上方向,"X" / "Y" / "Z"
    handedness: str  # "right" / "left"
    matrix: Matrix3 = IDENTITY
    #: 该约定是否对 UV 的 V 分量做 V→1-V(UE 导入器行为)。与 matrix 无关——UV 非 3D 线性变换。
    flip_uv_v: bool = False

    @property
    def is_mirror(self) -> bool:
        """变换是否翻转了手性(行列式为负)。由矩阵推出,不手工维护。"""
        return determinant3x3(self.matrix) < 0

    def apply(self, v: Vector3) -> Vector3:
        return apply3x3(self.matrix, v)

    @property
    def viewport_basis(self) -> Matrix3:
        """目标引擎坐标轴嵌入 Maya 固定 Y-up 视口后的显示基。"""
        return inverse3x3(self.matrix)


CONVENTIONS: dict[str, CoordConvention] = {
    "maya": CoordConvention(
        id="maya",
        label="Maya（参照，不变换）",
        up_axis="Y",
        handedness="right",
        matrix=IDENTITY,
    ),
    "ue": CoordConvention(
        id="ue",
        label="Unreal Engine（Z-up，左手）",
        up_axis="Z",
        handedness="left",
        matrix=MAYA_TO_UE,
        flip_uv_v=True,
    ),
}


def flip_uv_v(
    channels: dict[str, ChannelData],
    convention: CoordConvention,
    enabled: bool = True,
) -> dict[str, ChannelData]:
    """按坐标约定翻转 UV 通道的 V 分量(UE 导入器对每个 UV 的 V 做 V→1-V)。

    仅当 ``enabled`` 且 ``convention.flip_uv_v`` 为真时生效;只改 ``source`` 为 UV_SET 的通道的
    ``"V"`` 分量,U 分量与顶点色通道均不受影响。在**解码之前**作用于刚读出的 ``ChannelData``,
    因此所有解码器 / 校验器 / 可视化器看到的都是目标引擎空间的 V,忠实复现 UE"先翻 V 再解码"。

    ``channels`` 里的 ``ChannelData`` 是读取层每次新建的对象(逐元素 append),故原地改
    ``components["V"]`` 安全、不污染缓存,且保持 face-vertex 逐元素对齐。返回同一 dict 便于链式调用。
    """
    if not (enabled and convention.flip_uv_v):
        return channels
    for cd in channels.values():
        if cd.channel.source is SourceType.UV_SET and "V" in cd.components:
            cd.components["V"] = [1.0 - v for v in cd.components["V"]]
    return channels


def axis_label_map(convention: CoordConvention) -> dict[int, str]:
    """Maya 局部 X/Y/Z(下标 0/1/2)在该约定下分别对应引擎的哪根轴,供坐标轴 gizmo 标注文字。

    例如 UE 约定下,Maya 的 Y 轴(局部上方向)变换后落在 Z 上,返回的 ``{1: ...}`` 是 ``"Z (Up)"``。
    """
    labels: dict[int, str] = {}
    for i, name in enumerate(_AXIS_NAMES):
        basis: Vector3 = tuple(1.0 if j == i else 0.0 for j in range(3))  # type: ignore[assignment]
        mapped = convention.apply(basis)
        # 基向量变换后只有一个分量非零(matrix 的第 i 列即为该基向量的像)。
        idx = max(range(3), key=lambda k: abs(mapped[k]))
        sign = "-" if mapped[idx] < 0 else ""
        target = f"{sign}{_AXIS_NAMES[idx]}"
        if _AXIS_NAMES[idx] == convention.up_axis:
            target += " (Up)"
        labels[i] = target
    return labels


__all__ = [
    "CONVENTIONS",
    "CoordConvention",
    "IDENTITY",
    "MAYA_TO_UE",
    "Matrix3",
    "Vector3",
    "apply3x3",
    "axis_label_map",
    "determinant3x3",
    "flip_uv_v",
    "inverse3x3",
    "to_maya_matrix44",
    "view_rotation_from_matrix",
]
