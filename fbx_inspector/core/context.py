"""检查上下文(与 Maya 无关)。

`InspectionContext` 承载一次检查运行的共享状态:目标网格名、可视化前缀、
是否只校验不改场景等开关。之所以不直接持有 Maya 对象,是为了让编排逻辑与
规则装配保持可测试;真正的 `MeshData` 由 `api` 层在 Maya 内按名字解析。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InspectionContext:
    """一次检查运行的共享设置。"""

    mesh_name: str
    # 可视化写入的临时 color set 前缀,便于事后统一清理。
    visualize_prefix: str = "__inspector__"
    # 为 True 时只跑校验、不修改场景(批处理 / CI 场景)。
    validate_only: bool = False
