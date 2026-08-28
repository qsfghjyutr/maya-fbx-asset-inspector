"""高层编排入口。

这里把"按名字解析 Maya 网格"与"运行配置档、汇总报告"缝合起来。
解析网格触及 Maya(惰性导入);编排与报告本身与 Maya 无关。
"""

from __future__ import annotations

from .core.context import InspectionContext
from .report import Report, build_report
from .rules.profile import Profile


def run_profile(mesh_name: str, profile: Profile, *, validate_only: bool = False) -> Report:
    """对 Maya 场景里的一个网格运行整个配置档,返回报告。

    仅在 Maya 内可用:内部会构造读取网格的 `MeshData`。
    """
    from .core.mesh_data import MeshData  # 惰性:仅在真正跑检查时才需要 Maya

    ctx = InspectionContext(mesh_name=mesh_name, validate_only=validate_only)
    mesh = MeshData(mesh_name)
    results = profile.run(mesh, ctx)
    return build_report(mesh_name, results)


def clear_visualizations(mesh_name: str, profile: Profile) -> None:
    """清理某配置档在网格上留下的所有可视化 color set。"""
    from .core.mesh_data import MeshData

    ctx = InspectionContext(mesh_name=mesh_name)
    mesh = MeshData(mesh_name)
    for rule in profile.rules:
        if rule.visualizer is not None:
            rule.visualizer.clear(mesh, ctx)


__all__ = ["run_profile", "clear_visualizations", "Report"]
