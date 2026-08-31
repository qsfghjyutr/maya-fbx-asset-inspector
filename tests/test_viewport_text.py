"""Viewport 数值标签的数据整理测试（无需 Maya）。"""

from fbx_inspector.core.types import DataKind, DecodedData
from fbx_inspector.visualize.viewport import (
    DEFAULT_LABEL_COLOR,
    ViewportTextVisualizer,
    build_label_payload,
    build_vertex_labels,
    format_value,
)


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
    assert build_vertex_labels(data) == {3: "0.2 | 0.8"}


def test_coincident_geometry_vertices_share_one_unambiguous_label():
    labels = {0: "1", 1: "0.01", 2: "1"}
    positions = [(2.0, 3.0, 4.0), (2.0, 3.0, 4.0), (2.0, 3.0, 4.0)]
    assert build_label_payload(labels, positions) == [
        {"p": (2.0, 3.0, 4.0), "text": "1 | 0.01"}
    ]


def test_label_color_has_readable_default_and_is_clamped():
    assert DEFAULT_LABEL_COLOR == (230 / 255, 81 / 255, 0.0, 1.0)
    visualizer = ViewportTextVisualizer(color=(2.0, -1.0, 0.5, 1.0))
    assert visualizer.color == (1.0, 0.0, 0.5, 1.0)
