"""开箱即用的示例规则。

这些示例既能直接用,也是编写自定义规则的范本。导入本子包即会把示例配置档登记进
注册表(见 ``plugins.load_examples``)。示例代码属于系统核心的一部分,会随版本更新;
自定义规则应放到独立的用户规则目录,详见 ``fbx_inspector.plugins`` 与仓库根的
``user_rules/``。
"""

from __future__ import annotations

from . import vertex_color_channels as vertex_color_channels

__all__ = ["vertex_color_channels"]
