"""maya-fbx-asset-inspector —— 基于 Maya 2025 的 FBX 资产检查工具链。

顶层包只暴露稳定的公共入口;触及 Maya / PySide6 的子模块均为惰性导入,
因此在没有 Maya 的环境里 `import fbx_inspector` 也不会失败。
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
