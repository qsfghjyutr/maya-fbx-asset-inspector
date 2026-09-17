"""坐标约定(与 Maya 无关)。

维护"Maya 局部空间 → 目标引擎坐标约定"的数据变换,并派生目标引擎坐标轴在 Maya modelPanel
中的显示基。预览模型本身不换轴;坐标矩阵只负责轴方向和数值解释。不同引擎的 up 轴 / 手性不同,
这里的 ``matrix`` 是相对 Maya 当前世界空间的 3x3 线性变换——单位矩阵表示"跟 Maya 一致,不变换"。

⚠️ Maya 的世界上方向轴由环境设置决定,可为 **Y-up 或 Z-up**(``cmds.upAxis``),两者都是右手系。
因此约定集不是固定常量,而由 ``conventions_for(maya_up)`` 按检测到的上方向轴构造(打开检查器时读
一次)。顶层 ``CONVENTIONS`` 是 Y-up 基线(``conventions_for("y")``),供纯测试与向后兼容。

⚠️ Maya → Unreal Engine 的净换算**已对照 UE 5.8 源码逐行核实**(默认走 Interchange 的 FBX-SDK
后端,``bUseUfbxParser`` 默认 false),可精确分解为 ``S · R`` 两步:UE 先用
``FbxAxisSystem::ConvertScene`` 把场景转到 Z-up / front=-Y 的右手系(纯旋转 ``R``,det +1),再用
``FFbxConvert::ConvertPos`` 取反 Y(手性翻转 ``S`` = ``diag(1,-1,1)``,det -1)。位置与法线/切线走
**同一个**变换。源码见 ``Engine/Plugins/Interchange/.../Parsers/Fbx/Private/FbxConvert.{h,cpp}``
与 ``FbxMesh.cpp``。

关键推论:``R``(Y-up→Z-up)**只在 Maya 为 Y-up 时才需要**。Maya 本就是 Z-up 时数据已在 Z-up,
``R`` 退化为单位阵,净变换只剩手性翻转 ``S``——一个预览里看不见、且上方向(Z)与 Maya 一致的镜像。
故 ``maya_to_ue_matrix(maya_up) = S · rot``:Y-up 时 ``rot=R`` 得到历史上的 Y↔Z 互换(det -1);
Z-up 时 ``rot=I`` 只剩 ``diag(1,-1,1)``。若项目开 ``bForceFrontXAxis``(front=+X、关节额外
``Rot(-90,-90,0)``),净变换会不同——届时只需改本模块的常量,不影响其余代码。

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

import math
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

# Maya(Y-up,右手)→ UE(Z-up,左手)的历史净变换:X 不变,Y(up)搬到 Z,Z 搬到 Y。det -1。
# 保留为 Y-up 基线常量(向后兼容);等于 maya_to_ue_matrix("y")。分解见下方 _YUP_TO_ZUP / _UE_CHIRALITY。
MAYA_TO_UE: Matrix3 = (
    (1.0, 0.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, 1.0, 0.0),
)

# R:把 Y-up 数据抬成 Z-up 的纯旋转(绕世界 X +90°,Y→Z、Z→-Y),det +1。Maya 已是 Z-up 时不需要。
_YUP_TO_ZUP: Matrix3 = (
    (1.0, 0.0, 0.0),
    (0.0, 0.0, -1.0),
    (0.0, 1.0, 0.0),
)

# S:UE 导入器的手性步 —— 取反 Y(ConvertPos),det -1。与 up 轴无关,始终作用。
_UE_CHIRALITY: Matrix3 = (
    (1.0, 0.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, 0.0, 1.0),
)

_AXIS_NAMES = ("X", "Y", "Z")


def apply3x3(m: Matrix3, v: Vector3) -> Vector3:
    """把 3x3 矩阵作用在一个向量上(逐行点乘)。"""
    return tuple(sum(row[i] * v[i] for i in range(3)) for row in m)  # type: ignore[return-value]


def matmul3x3(a: Matrix3, b: Matrix3) -> Matrix3:
    """3x3 矩阵乘 ``a · b``(先作用 ``b`` 再作用 ``a``,与 ``apply3x3(a, apply3x3(b, v))`` 等价)。"""
    return tuple(  # type: ignore[return-value]
        tuple(sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3))
        for r in range(3)
    )


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


def _normalize3(v: Vector3) -> Vector3:
    mag = math.sqrt(sum(c * c for c in v))
    return tuple(c / mag for c in v) if mag > 1e-12 else v  # type: ignore[return-value]


def _cross3(a: Vector3, b: Vector3) -> Vector3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def orbit_camera_world_matrix(
    world_up_axis: str,
    azimuth_deg: float = 45.0,
    elevation_deg: float = 27.938,
    distance: float = 10.0,
) -> list[float]:
    """构造一台"看向原点"的 3/4 视角相机世界矩阵(Maya ``xform -matrix`` 用的 16 元组)。

    直接从朝向向量拼矩阵而非硬编码欧拉角,避免 rotateOrder 陷阱:相机 ``right`` 由
    ``forward × worldUp`` 得到,**必在水平面内(无 roll)**,于是世界上方向轴一定投影到屏幕正上方
    (水平分量为 0),Focus/取景不会歪。``world_up_axis`` 为 "y" 或 "z";平移仅占位,实际取景由
    调用方的 ``viewFit`` 沿视线修正。纯函数,可无头单测。
    """
    up = world_up_axis.lower()
    world_up: Vector3 = (0.0, 0.0, 1.0) if up == "z" else (0.0, 1.0, 0.0)
    az, el = math.radians(azimuth_deg), math.radians(elevation_deg)
    ce, se = math.cos(el), math.sin(el)
    # 眼睛方向:水平方位 az + 抬高 el,落在"右 / 前 / 上"象限(front 取 -水平第二轴)。
    if up == "z":
        eye_dir: Vector3 = (ce * math.sin(az), -ce * math.cos(az), se)
    else:  # y-up
        eye_dir = (ce * math.sin(az), se, ce * math.cos(az))
    forward = tuple(-d for d in eye_dir)  # 看向原点
    right = _normalize3(_cross3(forward, world_up))  # type: ignore[arg-type]
    cam_up = _normalize3(_cross3(right, forward))  # type: ignore[arg-type]
    local_z = tuple(-c for c in forward)  # 相机看 -Z,故局部 Z = -forward
    eye = tuple(d * distance for d in eye_dir)
    # 行主序、行向量约定:前三行 = 相机局部 X/Y/Z 世界方向,第四行 = 平移。
    return [
        right[0], right[1], right[2], 0.0,
        cam_up[0], cam_up[1], cam_up[2], 0.0,
        local_z[0], local_z[1], local_z[2], 0.0,
        eye[0], eye[1], eye[2], 1.0,
    ]


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
        """目标引擎坐标轴嵌入 Maya 当前世界视口(Y-up 或 Z-up)后的显示基。"""
        return inverse3x3(self.matrix)


def maya_to_ue_matrix(maya_up: str) -> Matrix3:
    """Maya(当前上方向轴)→ UE 的净变换 ``S · rot``。

    ``rot`` 在 Maya 为 Y-up 时是 Y-up→Z-up 旋转 ``R``(合成得到历史上的 Y↔Z 互换),在 Maya 已是
    Z-up 时退化为单位阵(数据已在 Z-up),此时净变换只剩手性翻转 ``diag(1,-1,1)``。两种情形 det 均为 -1。
    """
    rot = _YUP_TO_ZUP if maya_up.lower() == "y" else IDENTITY
    return matmul3x3(_UE_CHIRALITY, rot)


def maya_reference_convention(up_axis: str) -> CoordConvention:
    """Maya 参照约定:恒等变换(预览就在 Maya 当前世界系),上方向轴取检测值。"""
    up = up_axis.upper()  # 'y'/'z' → 'Y'/'Z'
    return CoordConvention(
        id="maya",
        label=f"Maya（参照，{up}-up，不变换）",
        up_axis=up,
        handedness="right",
        matrix=IDENTITY,
    )


def conventions_for(maya_up: str) -> dict[str, CoordConvention]:
    """按 Maya 实际上方向轴('y'/'z')构造完整约定集;maya 与 ue 都随之退化。"""
    return {
        "maya": maya_reference_convention(maya_up),
        "ue": CoordConvention(
            id="ue",
            label="Unreal Engine（Z-up，左手）",
            up_axis="Z",
            handedness="left",
            matrix=maya_to_ue_matrix(maya_up),
            flip_uv_v=True,
        ),
    }


#: Y-up 基线约定集,供纯测试与向后兼容;实际使用时按检测到的上方向轴调用 ``conventions_for``。
CONVENTIONS: dict[str, CoordConvention] = conventions_for("y")


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
    "conventions_for",
    "determinant3x3",
    "flip_uv_v",
    "inverse3x3",
    "matmul3x3",
    "maya_reference_convention",
    "maya_to_ue_matrix",
    "orbit_camera_world_matrix",
    "to_maya_matrix44",
    "view_rotation_from_matrix",
]
