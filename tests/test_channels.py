"""ui/channels.py 的单测(无需 Maya)。"""

from __future__ import annotations

from fbx_inspector.core.channel import SourceType
from fbx_inspector.core.remap import Ramp
from fbx_inspector.core.types import DataKind
from fbx_inspector.ui.channels import scalar_rule_for
from fbx_inspector.visualize.base import RAMPS


def test_color_channel_builds_scalar_rule():
    rule = scalar_rule_for(SourceType.COLOR_SET, "colorSet1", "R")
    assert rule.decoder.output_kind is DataKind.SCALAR
    assert rule.decoder.component == "R"
    assert rule.channel_roles["in"].name == "colorSet1"
    assert rule.visualizer.set_suffix == "view"
    assert len(rule.validators) == 1  # RangeCheck


def test_default_ramp_is_grayscale():
    rule = scalar_rule_for(SourceType.COLOR_SET, "colorSet1", "R")
    assert rule.visualizer.ramp is RAMPS["grayscale"]


def test_uv_channel_builds_scalar_rule():
    rule = scalar_rule_for(SourceType.UV_SET, "map1", "U", curve=Ramp.quadratic())
    assert rule.decoder.component == "U"
    assert rule.channel_roles["in"].source is SourceType.UV_SET
    assert rule.visualizer.curve is not None


def test_invalid_component_rejected():
    for src, name, comp in [
        (SourceType.COLOR_SET, "cs", "U"),  # 颜色没有 U
        (SourceType.UV_SET, "uv", "R"),     # UV 没有 R
    ]:
        try:
            scalar_rule_for(src, name, comp)
        except ValueError:
            continue
        raise AssertionError(f"非法分量 {comp} 应报 ValueError")


def test_no_range_check_when_disabled():
    rule = scalar_rule_for(SourceType.COLOR_SET, "cs", "G", check_range=False)
    assert rule.validators == []
