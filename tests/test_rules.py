"""规则装配与报告的端到端单测(无需 Maya,用 FakeMesh)。"""

from __future__ import annotations

from fbx_inspector.core.context import InspectionContext
from fbx_inspector.core.types import DataKind, DecodedData, RuleResult, VisualizeInfo
from fbx_inspector.decode.builtin import ScalarFromComponent
from fbx_inspector.report import build_report
from fbx_inspector.rules.profile import Profile, Rule
from fbx_inspector.validate.builtin import RangeCheck
from fbx_inspector.visualize.colorset import ColorSetRemapVisualizer

from .conftest import make_uv_mesh


def _ao_rule() -> Rule:
    _, chan = make_uv_mesh([0.0])
    return Rule(
        id="ao_from_uv2",
        decoder=ScalarFromComponent(component="U"),
        channel_roles={"in": chan},
        visualizer=None,  # 不触及 Maya
        validators=[RangeCheck(0.0, 1.0)],
    )


def test_rule_runs_decode_and_validate():
    mesh, _ = make_uv_mesh([0.2, 0.5, 1.4])  # 第三个越界
    ctx = InspectionContext(mesh_name="pSphere1", validate_only=True)
    result = _ao_rule().run(mesh, ctx)
    assert result.rule_id == "ao_from_uv2"
    assert result.error_count == 1
    assert result.visualized is False


def test_profile_matches_and_report_serializes():
    mesh, _ = make_uv_mesh([0.2, 0.5, 1.4])
    profile = Profile(id="props", rules=[_ao_rule()], match_pattern=r"^prop_")
    assert profile.matches("prop_barrel")
    assert not profile.matches("char_hero")

    ctx = InspectionContext(mesh_name="prop_barrel", validate_only=True)
    report = build_report("prop_barrel", profile.run(mesh, ctx))
    assert report.passed is False
    assert report.total_errors == 1

    d = report.to_dict()
    assert d["asset"] == "prop_barrel"
    assert d["results"][0]["rule_id"] == "ao_from_uv2"
    # to_json 不应抛异常,且能保留中文
    assert "prop_barrel" in report.to_json()


def test_value_range_maya_free():
    data = DecodedData(
        kind=DataKind.SCALAR,
        values=[(0.2,), (0.7,), (0.35,)],
        vertex_ids=[0, 1, 2],
        face_ids=[0, 0, 0],
    )
    assert ColorSetRemapVisualizer.value_range(data) == (0.2, 0.7)


def test_report_shows_normalization_range():
    result = RuleResult(
        rule_id="view:colorSet1.R",
        visualized=True,
        viz_info=VisualizeInfo(normalized=True, data_min=0.2, data_max=0.7),
    )
    report = build_report("prop_barrel", [result])

    text = report.to_text()
    assert "归一化区间" in text
    assert "min=0.2" in text
    assert "max=0.7" in text

    norm = report.to_dict()["results"][0]["normalization"]
    assert norm == {"normalized": True, "data_min": 0.2, "data_max": 0.7}
