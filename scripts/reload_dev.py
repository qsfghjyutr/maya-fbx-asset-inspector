"""开发期在 Maya 内热重载 fbx_inspector。

Maya 的 Python 会话是常驻的:改了源文件后,``import`` 只会拿到 sys.modules 里缓存的旧模块。

注意:用 ``install.py`` 装好工具架按钮后,**按钮命令本身已内置这套重载**——每次点按钮都会先清缓存
再打开,开发期通常无需手动调用本函数。仅在需要从 Script Editor 手动重载时才用到它
(已装好后 ``fbx_inspector`` / ``scripts`` 均在 sys.path 上,无需再补路径):

    from scripts.reload_dev import reload_fbx_inspector
    reload_fbx_inspector()
    # 之后再重新 from fbx_inspector... import ...
"""

from __future__ import annotations

import sys


def reload_fbx_inspector() -> list[str]:
    """把所有 fbx_inspector 及动态加载的用户规则模块从 sys.modules 移除。

    返回被移除的模块名列表。移除后下一次 import 会重新读取最新源文件。
    """
    to_drop = [
        name
        for name in list(sys.modules)
        if name == "fbx_inspector"
        or name.startswith("fbx_inspector.")
        or name.startswith("fbx_user_rule__")
    ]
    for name in to_drop:
        del sys.modules[name]
    return to_drop


if __name__ == "__main__":
    print("已移除:", reload_fbx_inspector())
