"""LOD 名称解析与 Maya 场景发现。"""

from __future__ import annotations

import re

_LOD_SUFFIX = re.compile(r"^(.*?)(?:_|-)LOD(\d+)$", re.IGNORECASE)


def parse_lod_name(name: str) -> tuple[str, int] | None:
    """返回 DAG 短名中的资产前缀和 LOD 序号。"""
    match = _LOD_SUFFIX.match(name.rsplit("|", 1)[-1])
    return (match.group(1), int(match.group(2))) if match else None


def discover_lod_meshes(node: str) -> dict[int, str]:
    """从选中网格或组发现同资产 LOD；无后缀的单网格视作 LOD0。"""
    import maya.cmds as cmds  # type: ignore[import-not-found]

    long_names = cmds.ls(node, long=True) or []
    if not long_names:
        raise RuntimeError(f"找不到节点：{node}")
    selected = long_names[0]
    if cmds.nodeType(selected) == "mesh":
        selected = (cmds.listRelatives(selected, parent=True, fullPath=True) or [selected])[0]

    def is_mesh_transform(item: str) -> bool:
        shapes = cmds.listRelatives(item, shapes=True, noIntermediate=True, fullPath=True) or []
        return any(cmds.nodeType(shape) == "mesh" for shape in shapes)

    selected_is_mesh = is_mesh_transform(selected)
    selected_info = parse_lod_name(selected) if selected_is_mesh else None
    if selected_info:
        parent = cmds.listRelatives(selected, parent=True, fullPath=True) or []
        candidates = (
            cmds.listRelatives(parent[0], children=True, type="transform", fullPath=True)
            if parent else [selected]
        ) or []
    else:
        candidates = cmds.listRelatives(
            selected, allDescendents=True, type="transform", fullPath=True
        ) or []
        if selected_is_mesh:
            candidates.append(selected)

    meshes = [item for item in candidates if is_mesh_transform(item)]
    parsed = [(item, parse_lod_name(item)) for item in meshes]
    if selected_info:
        prefix = selected_info[0].casefold()
        result = {
            info[1]: item for item, info in parsed
            if info is not None and info[0].casefold() == prefix
        }
        if result:
            return dict(sorted(result.items()))
    else:
        named = [(item, info) for item, info in parsed if info is not None]
        if len({info[0].casefold() for _, info in named}) == 1 and named:
            return dict(sorted((info[1], item) for item, info in named))

    if selected_is_mesh:
        return {0: selected}
    if len(meshes) == 1:
        return {0: meshes[0]}
    raise RuntimeError("所选组中无法确定 LOD；请按 Asset_LOD0、Asset_LOD1 命名。")
