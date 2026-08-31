"""把 FBX Inspector 安装到 Maya 工具架(shelf)。

**推荐:拖拽安装** —— 在资源管理器里把本文件拖进 Maya 视口,自动完成安装,全程无需输入任何路径。
(备选:Maya 菜单 File → Source Script… 选中本文件也可。)

安装内容:
  1. 把本仓库根目录加入当前会话的 sys.path(立即可用);
  2. 写入 <maya>/scripts/userSetup.py(幂等),使重启 Maya 后仍能 import;
  3. 在 Maya 用户 plug-ins 目录安装一个通用可信加载桥,实际插件代码仍从仓库读取;
  4. 在 Maya 内置 UV Editing(中文显示为“UV 编辑”)工具架上创建一个 "FBXi" 按钮。

为何需要加载桥:Inspector 本体是普通 Python 包,加入 sys.path 即可,不会经过 Maya 的插件安全
检查;数值标签使用 MPxLocatorNode / MPxDrawOverride,必须由 cmds.loadPlugin 注册。若直接从仓库
加载,Maya 会把仓库判为非可信插件位置并在每个新会话警告。可信目录中只复制一个通用稳定入口,
所有当前及未来的 Maya 插件模块都通过它注册;功能实现仍从仓库导入,因此保留“一次安装、仓库代码
自动更新”的开发体验。

仓库位置由本文件的 ``__file__`` 自动推导,**不含任何硬编码路径**。

按钮命令内置模块重载:每次点击都会清掉缓存的 fbx_inspector 模块再打开,因此**开发期改完代码
直接点按钮就能看到最新效果**,无需手动 reload。

卸载:``import install; install.uninstall()``(或拖拽后在 Script Editor 里调用)。
"""

from __future__ import annotations

import os
import shutil
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
_SHELF_NAME = "UVEditing"
_PLUGIN_ID = "fbx_inspector_plugin"
_PLUGIN_FILENAME = f"{_PLUGIN_ID}.py"
_PLUGIN_LOADER = os.path.join(_REPO, _PLUGIN_FILENAME)
_LEGACY_PLUGIN_IDS = ("fbx_inspector_viewport", "viewport_plugin")
_LABEL_NODE_TYPE = "fbxInspectorValueLabels"


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


def _plugin_target() -> str:
    """当前 Maya 版本的用户插件目录中的通用加载桥路径。"""
    import maya.cmds as cmds  # type: ignore[import-not-found]

    directory = os.path.join(
        cmds.internalVar(userAppDir=True), str(cmds.about(version=True)), "plug-ins"
    )
    return os.path.join(directory, _PLUGIN_FILENAME)


def _plugin_loaded(plugin_id: str) -> bool:
    import maya.cmds as cmds  # type: ignore[import-not-found]

    try:
        return bool(cmds.pluginInfo(plugin_id, query=True, loaded=True))
    except RuntimeError:
        return False


def _remove_label_nodes() -> None:
    import maya.cmds as cmds  # type: ignore[import-not-found]

    for shape in cmds.ls(type=_LABEL_NODE_TYPE, long=True) or []:
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        cmds.delete(parents[0] if parents else shape)


def _unload_inspector_plugins() -> None:
    """卸载通用可信桥及旧版 Viewport 专用加载入口。"""
    import maya.cmds as cmds  # type: ignore[import-not-found]

    loaded = [
        plugin_id for plugin_id in (_PLUGIN_ID, *_LEGACY_PLUGIN_IDS)
        if _plugin_loaded(plugin_id)
    ]
    if not loaded:
        return
    _remove_label_nodes()
    for plugin_id in loaded:
        cmds.unloadPlugin(plugin_id, force=True)


def _install_plugin_bridge() -> str:
    """安装通用稳定加载桥；所有功能实现始终来自仓库。"""
    import maya.cmds as cmds  # type: ignore[import-not-found]

    target = _plugin_target()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    _unload_inspector_plugins()
    legacy_bridge = os.path.join(os.path.dirname(target), "fbx_inspector_viewport.py")
    if os.path.exists(legacy_bridge):
        os.remove(legacy_bridge)
    shutil.copy2(_PLUGIN_LOADER, target)
    # 自动加载可能早于 userSetup.py,故把仓库位置写入桥的已安装副本。这里只写路径配置,
    # Viewport 功能实现仍留在仓库,不会被复制。
    with open(target, "a", encoding="utf-8") as f:
        f.write(f"\n_REPO_OVERRIDE = {_REPO!r}\n")
    cmds.loadPlugin(target, quiet=True)
    cmds.pluginInfo(_PLUGIN_ID, edit=True, autoload=True)
    return target


def _shelf_top_level() -> str:
    import maya.mel as mel  # type: ignore[import-not-found]

    return mel.eval("$tmp = $gShelfTopLevel")


def _all_shelves() -> list[str]:
    import maya.cmds as cmds  # type: ignore[import-not-found]

    return cmds.tabLayout(_shelf_top_level(), query=True, childArray=True) or []


def _target_shelf() -> str:
    """返回 Maya 内置 UV Editing Shelf；显示名由 Maya 负责本地化。"""
    for shelf in _all_shelves():
        if shelf.rsplit("|", 1)[-1] == _SHELF_NAME:
            return shelf
    raise RuntimeError(
        f"找不到 Maya 内置工具架 '{_SHELF_NAME}'；为保护 Shelf 配置，安装已停止。"
    )


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


def _remove_all_existing_buttons() -> None:
    for shelf in _all_shelves():
        _remove_existing_button(shelf)


def install() -> None:
    """执行安装:加 path、写 userSetup、安装插件桥、建工具架按钮。"""
    _ensure_on_path()
    us = _persist_path()
    bridge = _install_plugin_bridge()
    _remove_all_existing_buttons()
    shelf = _target_shelf()
    _make_button(shelf)
    print(f"[FBX Inspector] 已在工具架 '{shelf}' 上创建按钮。")
    print(f"[FBX Inspector] 路径已写入 {us},重启 Maya 后依然可用。")
    print(f"[FBX Inspector] 通用 Maya 插件可信加载桥已安装: {bridge}")


def uninstall() -> None:
    """移除工具架按钮、启动路径与通用 Maya 插件可信加载桥。"""
    _remove_all_existing_buttons()

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
    import maya.cmds as cmds  # type: ignore[import-not-found]

    if _plugin_loaded(_PLUGIN_ID):
        cmds.pluginInfo(_PLUGIN_ID, edit=True, autoload=False)
    _unload_inspector_plugins()
    target = _plugin_target()
    if os.path.exists(target):
        os.remove(target)
    print("[FBX Inspector] 已卸载工具架按钮、启动路径与通用 Maya 插件加载桥。")


def onMayaDroppedPythonFile(*args) -> None:
    """把本文件拖进 Maya 视口时,Maya 会调用此函数。"""
    install()
