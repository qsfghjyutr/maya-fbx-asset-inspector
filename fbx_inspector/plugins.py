"""插件发现与加载:让用户规则与系统核心分离。

系统核心是 ``fbx_inspector`` 包本身,会随版本更新;而**用户自己编写的规则 .py 与配置表**
应放在独立目录,从而在升级系统时不被覆盖、可直接在新版本上运行。本模块负责在运行时扫描
这些独立目录并导入其中的 .py(其内的 ``@decoder``/``@validator``/``register_profile`` 等
登记调用即会生效)。

扫描的用户规则目录(按顺序,去重):
  1. 环境变量 ``FBX_INSPECTOR_RULE_PATH``(可用 os.pathsep 分隔多个);
  2. 仓库根的 ``user_rules/``(随仓库分发,新增文件为未跟踪状态,git 更新不会改动);
  3. 用户主目录 ``~/.fbx_inspector/rules``(完全在系统之外,最不易被覆盖)。

文件名以下划线开头的会被跳过(视为模板/私有,如 ``_template.py``)。
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

ENV_VAR = "FBX_INSPECTOR_RULE_PATH"


def _repo_user_rules_dir() -> Path:
    # plugins.py 位于 <repo>/fbx_inspector/plugins.py
    return Path(__file__).resolve().parent.parent / "user_rules"


def user_rule_dirs() -> list[Path]:
    """返回要扫描的用户规则目录列表(去重,保序;不要求已存在)。"""
    dirs: list[Path] = []
    env = os.environ.get(ENV_VAR)
    if env:
        dirs += [Path(p) for p in env.split(os.pathsep) if p.strip()]
    dirs.append(_repo_user_rules_dir())
    dirs.append(Path.home() / ".fbx_inspector" / "rules")

    seen: set[Path] = set()
    out: list[Path] = []
    for d in dirs:
        try:
            key = d.resolve()
        except OSError:
            key = d
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def load_file(path: str | Path) -> ModuleType | None:
    """按路径导入单个 .py;下划线开头者跳过。已导入过则返回缓存,避免重复登记。"""
    path = Path(path)
    if path.name.startswith("_") or path.suffix != ".py":
        return None
    mod_name = f"fbx_user_rule__{path.stem}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


def load_dir(directory: str | Path) -> list[str]:
    """导入目录下所有 .py,返回成功加载的文件名。目录不存在则返回空。"""
    d = Path(directory)
    if not d.is_dir():
        return []
    loaded: list[str] = []
    for py in sorted(d.glob("*.py")):
        if load_file(py) is not None:
            loaded.append(py.name)
    return loaded


def load_examples() -> None:
    """导入内置示例,使其配置档被登记。"""
    importlib.import_module("fbx_inspector.examples.vertex_color_channels")


def discover(*, include_examples: bool = True) -> list[str]:
    """发现并加载所有示例与用户规则。返回已加载条目的可读列表(便于日志)。"""
    loaded: list[str] = []
    if include_examples:
        load_examples()
        loaded.append("examples")
    for d in user_rule_dirs():
        loaded += load_dir(d)
    return loaded
