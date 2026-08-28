"""core/context.py 的单测(无需 Maya)。"""

from __future__ import annotations

from fbx_inspector.core.context import InspectionContext


def test_defaults_are_maya_and_convert_uv_on():
    ctx = InspectionContext(mesh_name="pSphere1")
    assert ctx.coord_convention_id == "maya"
    assert ctx.convert_uv is True
    assert ctx.validate_only is False
