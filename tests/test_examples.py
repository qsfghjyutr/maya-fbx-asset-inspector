"""示例规则单测(无需 Maya)。"""

from __future__ import annotations

from fbx_inspector.core.context import InspectionContext
from fbx_inspector.core.registry import PROFILES
from fbx_inspector.examples.vertex_color_channels import (
    CHANNELS,
    channel_view_rule,
    vertex_color_channels_profile,
)
from fbx_inspector.report import build_report

from .conftest import FakeMesh
from fbx_inspector.core.channel import Channel, SourceType


def _color_mesh(n=6):
    chan = Channel(SourceType.COLOR_SET, "colorSet1")
    comps = {
        "R": [i / (n - 1) for i in range(n)],
        "G": [0.5] * n,
        "B": [0.0] * n,
        "A": [1.0] * n,
    }
    mesh = FakeMesh({chan: comps}, list(range(n)), [0] * n)
    return mesh, chan


def test_profile_has_one_rule_per_channel():
    profile = vertex_color_channels_profile("colorSet1")
    assert len(profile.rules) == len(CHANNELS)
    # 每条规则写入不同后缀的 color set,避免互相覆盖
    suffixes = {r.visualizer.set_suffix for r in profile.rules}
    assert suffixes == set(CHANNELS)


def test_channel_rule_runs_validate_only():
    mesh, _ = _color_mesh()
    rule = channel_view_rule("colorSet1", "R")  # 数据在 [0,1] 内
    ctx = InspectionContext(mesh_name="m", validate_only=True)
    result = rule.run(mesh, ctx)
    assert result.error_count == 0
    assert result.visualized is False  # validate_only 不触发可视化


def test_curved_rule_uses_distinct_suffix():
    from fbx_inspector.core.remap import Ramp

    rule = channel_view_rule("colorSet1", "R", curve=Ramp.quadratic())
    assert rule.visualizer.set_suffix == "R_curved"
    assert rule.visualizer.curve is not None


def test_example_profiles_are_registered():
    ids = PROFILES.ids()
    assert "vertex_color_channels:colorSet1" in ids
    assert "vertex_color_channels:colorSet1:quadratic" in ids
