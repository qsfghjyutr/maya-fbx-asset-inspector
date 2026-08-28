"""PySide6 用户界面(仅 Maya,惰性导入)。

对外入口是 ``open_inspector``:在 Maya 内打开独立检查窗口。为使本包在无 Maya / 无 Qt 环境
也能被 import,这里用 ``__getattr__`` 惰性转发,真正的实现只在调用时才导入。
"""

from __future__ import annotations


def __getattr__(name: str):
    if name == "open_inspector":
        from .window import open_inspector

        return open_inspector
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["open_inspector"]
