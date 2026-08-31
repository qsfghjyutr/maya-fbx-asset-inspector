"""FBX Inspector 所有 Maya 插件扩展的统一聚合入口。

可信目录中只有一个 ``fbx_inspector_plugin.py`` 桥。以后新增 MPxNode、DrawOverride 等插件模块时，
只需把模块路径加入 ``PLUGIN_MODULES``，无需安装额外加载桥。
"""

from __future__ import annotations

from importlib import import_module

PLUGIN_MODULES = (
    "fbx_inspector.visualize.viewport_plugin",
)


def initialize_plugin(obj) -> None:
    """按声明顺序注册所有 Maya 插件模块。"""
    initialized = []
    try:
        for module_name in PLUGIN_MODULES:
            module = import_module(module_name)
            module.initializePlugin(obj)
            initialized.append(module)
    except Exception:
        for module in reversed(initialized):
            module.uninitializePlugin(obj)
        raise


def uninitialize_plugin(obj) -> None:
    """按注册的逆序卸载所有 Maya 插件模块。"""
    for module_name in reversed(PLUGIN_MODULES):
        import_module(module_name).uninitializePlugin(obj)


__all__ = ["PLUGIN_MODULES", "initialize_plugin", "uninitialize_plugin"]
