"""把 FBX Inspector 安装到 Maya 工具架(shelf)。

**推荐:拖拽安装** —— 在资源管理器里把本文件拖进 Maya 视口,自动完成安装,全程无需输入任何路径。
(备选:Maya 菜单 File → Source Script… 选中本文件也可。)

安装内容:
  1. 把本仓库根目录加入当前会话的 sys.path(立即可用);
  2. 写入 <maya>/scripts/userSetup.py(幂等),使重启 Maya 后仍能 import;
  3. 在当前工具架上创建一个 "FBXi" 按钮,点击即打开检查窗口。

仓库位置由本文件的 ``__file__`` 自动推导,**不含任何硬编码路径**。

按钮命令内置模块重载:每次点击都会清掉缓存的 fbx_inspector 模块再打开,因此**开发期改完代码
直接点按钮就能看到最新效果**,无需手动 reload。

卸载:``import install; install.uninstall()``(或拖拽后在 Script Editor 里调用)。
"""

from __future__ import annotations

import os
import sys

# 仓库根目录 = 本文件所在目录。自动推导,绝不硬编码。
_REPO = os.path.dirname(os.path.abspath(__file__))

# 工具架按钮执行的命令:先清缓存再打开(保证用最新代码)。
_LAUNCH_CMD = """import sys
for _m in [x for x in list(sys.modules)
           if x == "fbx_inspector" or x.startswith("fbx_inspector.")
           or x.startswith("fbx_user_rule__")]:
    del sys.modules[_m]
from fbx_inspector.ui import open_inspector
open_inspector()"""

_MARK_BEGIN = "# >>> fbx_inspector path >>>"
_MARK_END = "# <<< fbx_inspector path <<<"
_BUTTON_LABEL = "FBX Inspector"


def _ensure_on_path() -> None:
    if _REPO not in sys.path:
        sys.path.insert(0, _REPO)


def _usersetup_path() -> str:
    import maya.cmds as cmds  # type: ignore[import-not-found]

    return os.path.join(cmds.internalVar(userScriptDir=True), "userSetup.py")


def _persist_path() -> str:
    """把仓库路径写进 userSetup.py(幂等),重启后仍可 import。返回文件路径。

    写入的路径同样来自 ``__file__`` 推导,是安装时在本机生成的配置,而非源码里的硬编码。
    """
    us = _usersetup_path()
    existing = ""
    if os.path.exists(us):
        with open(us, encoding="utf-8") as f:
            existing = f.read()
    if _MARK_BEGIN in existing:
        return us  # 已写过,不重复
    block = (
        f"{_MARK_BEGIN}\n"
        "import os, sys\n"
        f"_p = {os.path.abspath(_REPO)!r}\n"
        "if os.path.isdir(_p) and _p not in sys.path:\n"
        "    sys.path.append(_p)\n"
        f"{_MARK_END}\n"
    )
    with open(us, "a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(block)
    return us


def _current_shelf() -> str:
    import maya.cmds as cmds  # type: ignore[import-not-found]
    import maya.mel as mel  # type: ignore[import-not-found]

    top = mel.eval("$tmp = $gShelfTopLevel")
    return cmds.tabLayout(top, query=True, selectTab=True)


def _remove_existing_button(shelf: str) -> None:
    import maya.cmds as cmds  # type: ignore[import-not-found]

    for btn in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
        try:
            if cmds.shelfButton(btn, query=True, label=True) == _BUTTON_LABEL:
                cmds.deleteUI(btn)
        except RuntimeError:
            continue  # 非 shelfButton(如分隔符),跳过


def _make_button(shelf: str) -> str:
    import maya.cmds as cmds  # type: ignore[import-not-found]

    _remove_existing_button(shelf)
    return cmds.shelfButton(
        parent=shelf,
        label=_BUTTON_LABEL,
        annotation="打开 FBX 资产检查窗口(点击即重载最新代码)",
        image1="pythonFamily.png",
        imageOverlayLabel="FBXi",
        sourceType="python",
        command=_LAUNCH_CMD,
    )


def install() -> None:
    """执行安装:加 path、写 userSetup、建工具架按钮。"""
    _ensure_on_path()
    us = _persist_path()
    shelf = _current_shelf()
    _make_button(shelf)
    print(f"[FBX Inspector] 已在工具架 '{shelf}' 上创建按钮。")
    print(f"[FBX Inspector] 路径已写入 {us},重启 Maya 后依然可用。")


def uninstall() -> None:
    """移除工具架按钮,并从 userSetup.py 删除路径块。"""
    shelf = _current_shelf()
    _remove_existing_button(shelf)

    us = _usersetup_path()
    if os.path.exists(us):
        with open(us, encoding="utf-8") as f:
            text = f.read()
        if _MARK_BEGIN in text and _MARK_END in text:
            head, _, rest = text.partition(_MARK_BEGIN)
            _, _, tail = rest.partition(_MARK_END)
            cleaned = (head.rstrip("\n") + "\n" + tail.lstrip("\n")).strip()
            with open(us, "w", encoding="utf-8") as f:
                f.write(cleaned + ("\n" if cleaned else ""))
    print("[FBX Inspector] 已卸载工具架按钮与启动路径。")


def onMayaDroppedPythonFile(*args) -> None:
    """把本文件拖进 Maya 视口时,Maya 会调用此函数。"""
    install()
