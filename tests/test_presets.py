"""内置检查预设测试（无需 Maya）。"""

from fbx_inspector.core.registry import PROFILES
from fbx_inspector.presets.default import DEFAULT_PROFILE_ID, default_profile


def test_default_preset_is_registered_and_is_the_template_baseline():
    profile = default_profile()
    assert profile.id == DEFAULT_PROFILE_ID
    assert profile.display_name == "默认"
    assert [rule.id for rule in profile.rules] == [
        "default_colorSet1_R",
        "default_colorSet1_G",
        "default_colorSet1_B",
        "default_colorSet1_A",
    ]
    assert PROFILES.get(DEFAULT_PROFILE_ID).display_name == "默认"
