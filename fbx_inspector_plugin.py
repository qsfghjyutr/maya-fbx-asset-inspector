"""安装到 Maya 可信插件目录的 FBX Inspector 通用加载桥。

本文件不包含功能实现，只将 Maya 插件生命周期转发给仓库中的统一聚合入口
``fbx_inspector.maya_plugin``。未来新增的 MPxNode、DrawOverride 等模块都由该聚合入口管理，
无需再向 Maya 的可信目录复制其他加载器。
"""

from __future__ import annotations

import os
import sys

# install.py 会在已安装副本末尾覆盖此值，确保自动加载早于 userSetup.py 时也能找到仓库。
_REPO_OVERRIDE: str | None = None


def _ensure_repo_path() -> None:
    if _REPO_OVERRIDE and os.path.isdir(_REPO_OVERRIDE) and _REPO_OVERRIDE not in sys.path:
        sys.path.insert(0, _REPO_OVERRIDE)


def maya_useNewAPI():
    """通知 Maya 使用 Python API 2.0 调用插件入口。"""


def initializePlugin(obj):  # noqa: N802
    _ensure_repo_path()
    from fbx_inspector.maya_plugin import initialize_plugin

    initialize_plugin(obj)


def uninitializePlugin(obj):  # noqa: N802
    _ensure_repo_path()
    from fbx_inspector.maya_plugin import uninitialize_plugin

    uninitialize_plugin(obj)
