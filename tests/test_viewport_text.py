"""Viewport 数值标签的数据整理测试（无需 Maya）。"""

from fbx_inspector.core.types import DataKind, DecodedData
from fbx_inspector.visualize.viewport import build_vertex_labels, format_value


def test_format_value_is_compact():
    assert format_value((0.5001,), precision=3) == "0.5"
    assert format_value((-0.0,), precision=3) == "0"
    assert format_value((0.25, 1.0), precision=2) == "(0.25, 1)"


def test_face_vertex_values_merge_per_geometry_vertex():
    data = DecodedData(
        DataKind.SCALAR,
        values=[(0.2,), (0.2,), (0.8,)],
        vertex_ids=[3, 3, 3],
        face_ids=[0, 1, 2],
    )
    assert build_vertex_labels(data) == {3: "0.2\n0.8"}
