"""坐标约定(与 Maya 无关)。

维护"Maya 局部空间 → 目标引擎坐标约定"的变换矩阵,供 `ui/viewport_panel.py` 把隔离视口里的副本
摆成目标引擎导入后的姿态,以及 `ui/axis_gizmo.py` 给坐标轴打标签。Maya 是 **Y-up、右手系**;不同
引擎的 up 轴 / 手性不同,这里的 ``matrix`` 是相对 Maya 局部空间的 3x3 线性变换——单位矩阵表示
"跟 Maya 一致,不变换"。

⚠️ Maya → Unreal Engine 的默认换算(X 不变、Y↔Z 互换,即 up 轴从 Y 换到 Z)。这不是随手取的
"业界惯例",而是**已对照 UE 5.8 源码逐行核实**的导入器净变换(默认走 Interchange 的 FBX-SDK
后端,``bUseUfbxParser`` 默认 false):UE 先用 ``FbxAxisSystem::ConvertScene`` 把场景转到
Z-up / front=-Y 的右手系(纯旋转,det +1),再用 ``FFbxConvert::ConvertPos`` 取反 Y(det -1),
两步合成正好等于 X 不变、Y↔Z 互换,det = -1。位置与法线/切线走**同一个**变换。源码见
``Engine/Plugins/Interchange/.../Parsers/Fbx/Private/FbxConvert.{h,cpp}`` 与 ``FbxMesh.cpp``。

未在此矩阵内建模、但 UE 也会做的事(因不影响副本在视口里的朝向,故与本模块无关):UV ``V→1-V``、
单位缩放到 cm、binormal 额外取一次反。项目若开 ``bForceFrontXAxis``(front=+X、关节额外
``Rot(-90,-90,0)``),净变换会不同——届时只需改 ``CONVENTIONS`` 这一处常量,不影响其余代码。

关键的正确性提示:Maya(右手)→ UE(左手)是**换手性**(矩阵行列式为负,即镜像),不是纯旋转——
纯旋转的行列式恒为 +1,做不出手性翻转。``CoordConvention.is_mirror`` 由行列式推出,保证矩阵本身
与"是否需要翻转法线/绕序"这条业务判断永远自洽,不会因为手工维护两处标记而脱节。注意 UE 自己
**不翻绕序**,而是靠左手系 front=CW 把镜像后的三角面渲成正面;副本渲染在 Maya 右手视口里,
故 ``viewport_panel.set_coord_convention`` 需反转一次法线/绕序来补偿——这一步的**视觉**效果只能在
Maya GUI 手测(见 ``scripts/maya_smoke_test.py`` 第 [7] 节末尾的手测清单)。
"""

from __future__ import annotations

from dataclasses import dataclass

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

    @property
    def is_mirror(self) -> bool:
        """变换是否翻转了手性(行列式为负)。由矩阵推出,不手工维护。"""
        return determinant3x3(self.matrix) < 0

    def apply(self, v: Vector3) -> Vector3:
        return apply3x3(self.matrix, v)


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
    ),
}


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
    "to_maya_matrix44",
    "view_rotation_from_matrix",
]
