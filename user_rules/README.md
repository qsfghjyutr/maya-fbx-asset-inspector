# user_rules —— 你的规则目录（不会被系统更新覆盖）

这个目录是给**你自己**放规则代码和配置表的地方，独立于系统核心（`fbx_inspector/` 包）。
系统升级时只会更新 `fbx_inspector/`，你在这里新增的文件是 git 未跟踪的，不会被覆盖，可以直接
在新版本上继续运行。

## 怎么用

1. 复制本目录下的 `_template.py` 为你自己的文件，例如 `my_studio_rules.py`
   （**不要**用下划线开头命名——下划线开头的文件会被加载器当作模板跳过）。
2. 修改 `_build_profile()` 中的 Rule。可以只组合内置 Decoder / Visualizer / Validator，也可以在
   同一文件里定义自己的实现。
3. 为每个 Profile 设置唯一 `id`、界面名称 `name`、说明 `description` 和可选的
   `match_pattern`，然后用 `register_profile(..., overwrite=True)` 登记。一个文件可以登记多套预设。
4. 从 Maya 工具架重新打开 FBX Inspector。检查器会自动扫描用户目录，新 Profile 会出现在
   “检查预设”下拉框中；点击“一键执行全部规则”即可运行该 Profile 的所有检查和可视化规则。

也可以脱离 UI 手动检查注册结果：

   ```python
   from fbx_inspector import plugins
   plugins.discover()            # API 默认加载内置示例 + 所有用户规则目录
   from fbx_inspector.core.registry import PROFILES
   print(PROFILES.ids())         # 应能看到你登记的配置档 id
   ```

## 加载器会扫描哪些目录

按顺序（见 `fbx_inspector/plugins.py`）：

1. 环境变量 `FBX_INSPECTOR_RULE_PATH`（可用系统分隔符分隔多个目录）——推荐工作室把
   共享规则库指到这里；
2. 本目录 `user_rules/`；
3. 用户主目录 `~/.fbx_inspector/rules`。

配置表等数据文件也可以放在这些目录里，由你的规则代码自行读取。

## 默认预设与 Template

内置“默认”预设用于零门槛体验：它为 `colorSet1` 生成四套灰度显示，不强制通道值域，也不限制
UV 集数量；源码中保留了启用数量限制及 LOD 分级覆盖的注释示例。`_template.py` 是工作室规则的
可编辑起点，默认示范“全部 LOD 均要求 2 个 UV 集”，而 LOD1 的不同要求仅以注释展示。

`preflight_checks=[UVSetCountCheck(expected=2)]` 默认检查资产的全部 LOD。只有确实存在分级规范时，
才配置 `lod_preflight_checks={1: [UVSetCountCheck(expected=1)]}`；相同检查 id 会覆盖该 LOD 的
默认要求。前置检查失败时不会进入可视化阶段。

注意：

- 文件名必须以 `.py` 结尾且不能以下划线开头；
- 修改已加载的规则后，应重新点击 FBXi 工具架按钮，让模块缓存和注册表一起重载；
- 多套 Profile 的 `id` 不应重复；有意替换同 id 时使用 `overwrite=True`；
- 预设批量执行后，检查器会恢复并刷新执行前正在手动查看的通道，同时保留完整预设报告。
