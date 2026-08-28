"""规则装配与报告的端到端单测(无需 Maya,用 FakeMesh)。"""

from __future__ import annotations

from fbx_inspector.core.channel import Channel, SourceType
from fbx_inspector.core.context import InspectionContext
from fbx_inspector.core.types import DataKind, DecodedData, Issue, RuleResult, VisualizeInfo
from fbx_inspector.decode.builtin import ScalarFromComponent
from fbx_inspector.report import build_report
from fbx_inspector.rules.profile import Profile, Rule
from fbx_inspector.validate.base import Validator
from fbx_inspector.validate.builtin import RangeCheck
from fbx_inspector.visualize.colorset import ColorSetRemapVisualizer

from .conftest import FakeMesh, make_uv_mesh


class _CaptureValidator(Validator):
    """把收到的 DecodedData 存到自身,供测试直接断言解码后的值。不产生 Issue。"""

    def __init__(self) -> None:
        self.captured: DecodedData | None = None

    def validate(self, data: DecodedData) -> list[Issue]:
        self.captured = data
        return []


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


def _v_rule(chan, capture: _CaptureValidator) -> Rule:
    return Rule(
        id="v_channel",
        decoder=ScalarFromComponent(component="V"),
        channel_roles={"in": chan},
        visualizer=None,
        validators=[capture],
    )


def test_rule_run_flips_v_under_ue_convention():
    # 0.25/0.75 精确可表示,1-v 不会有舍入误差。
    chan = Channel(SourceType.UV_SET, "uvSet2")
    mesh = FakeMesh(
        channels={chan: {"U": [0.1, 0.9], "V": [0.25, 0.75]}},
        vertex_ids=[0, 1],
        face_ids=[0, 0],
    )
    ctx = InspectionContext(
        mesh_name="pSphere1", validate_only=True,
        coord_convention_id="ue", convert_uv=True,
    )
    capture = _CaptureValidator()
    _v_rule(chan, capture).run(mesh, ctx)
    assert capture.captured is not None
    assert capture.captured.values == [(0.75,), (0.25,)]  # V→1-V 后校验器看到的值


def test_rule_run_default_context_does_not_flip_v():
    chan = Channel(SourceType.UV_SET, "uvSet2")
    mesh = FakeMesh(
        channels={chan: {"U": [0.1, 0.9], "V": [0.25, 0.75]}},
        vertex_ids=[0, 1],
        face_ids=[0, 0],
    )
    ctx = InspectionContext(mesh_name="pSphere1", validate_only=True)  # 默认 maya,不翻
    capture = _CaptureValidator()
    _v_rule(chan, capture).run(mesh, ctx)
    assert capture.captured is not None
    assert capture.captured.values == [(0.25,), (0.75,)]  # 原样,未翻转


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
