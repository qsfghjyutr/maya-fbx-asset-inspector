"""插件加载器单测(无需 Maya)。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fbx_inspector import plugins
from fbx_inspector.core.registry import PROFILES

_RULE_SRC = '''
from fbx_inspector.core.registry import register_profile
from fbx_inspector.rules.profile import Profile
register_profile(Profile(id="unittest:loaded_from_file"), overwrite=True)
'''

_SKIPPED_SRC = '''
from fbx_inspector.core.registry import register_profile
from fbx_inspector.rules.profile import Profile
register_profile(Profile(id="unittest:should_be_skipped"), overwrite=True)
'''


def test_load_dir_imports_and_registers():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "my_rule.py").write_text(_RULE_SRC, encoding="utf-8")
        # 下划线开头的文件应被跳过
        (Path(d) / "_skip.py").write_text(_SKIPPED_SRC, encoding="utf-8")

        loaded = plugins.load_dir(d)
        assert "my_rule.py" in loaded
        assert "_skip.py" not in loaded
        assert "unittest:loaded_from_file" in PROFILES.ids()
        assert "unittest:should_be_skipped" not in PROFILES.ids()


def test_load_dir_missing_returns_empty():
    assert plugins.load_dir("/no/such/dir/xyz") == []


def test_user_rule_dirs_honors_env(monkeypatch=None):
    # 不依赖 pytest fixture:手动设置/还原环境变量
    old = os.environ.get(plugins.ENV_VAR)
    try:
        os.environ[plugins.ENV_VAR] = os.pathsep.join(["/tmp/a", "/tmp/b"])
        dirs = [str(p) for p in plugins.user_rule_dirs()]
        assert any(x.replace("\\", "/").endswith("/tmp/a") for x in dirs)
        assert any(x.replace("\\", "/").endswith("/tmp/b") for x in dirs)
    finally:
        if old is None:
            os.environ.pop(plugins.ENV_VAR, None)
        else:
            os.environ[plugins.ENV_VAR] = old


def test_discover_loads_examples():
    plugins.discover()
    assert "vertex_color_channels:colorSet1" in PROFILES.ids()
