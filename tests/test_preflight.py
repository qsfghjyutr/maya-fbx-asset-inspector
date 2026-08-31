"""前置检查与 LOD 分级规则测试（无需 Maya）。"""

from fbx_inspector.rules.preflight import UVSetCountCheck
from fbx_inspector.rules.profile import Profile


class _Mesh:
    def __init__(self, names):
        self.names = names

    def uv_set_names(self):
        return list(self.names)


def test_uv_count_default_applies_to_every_lod():
    profile = Profile(id="asset", preflight_checks=[UVSetCountCheck(expected=2)])
    results = profile.run_preflight(
        {0: _Mesh(["map1", "uv2"]), 1: _Mesh(["map1"])}
    )
    assert len(results) == 2
    assert results[0].error_count == 0
    assert results[1].error_count == 1
    assert "LOD1" in results[1].rule_id


def test_lod_rule_overrides_default_by_check_id():
    profile = Profile(
        id="asset",
        preflight_checks=[UVSetCountCheck(expected=2)],
        lod_preflight_checks={1: [UVSetCountCheck(expected=1)]},
    )
    results = profile.run_preflight(
        {0: _Mesh(["map1", "uv2"]), 1: _Mesh(["map1"])}
    )
    assert all(result.error_count == 0 for result in results)


def test_uv_count_supports_range():
    check = UVSetCountCheck(minimum=1, maximum=2)
    assert check.run(_Mesh(["map1"]), 0).error_count == 0
    assert check.run(_Mesh(["map1", "uv2", "uv3"]), 0).error_count == 1
