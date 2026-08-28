# user_rules —— 你的规则目录（不会被系统更新覆盖）

这个目录是给**你自己**放规则代码和配置表的地方，独立于系统核心（`fbx_inspector/` 包）。
系统升级时只会更新 `fbx_inspector/`，你在这里新增的文件是 git 未跟踪的，不会被覆盖，可以直接
在新版本上继续运行。

## 怎么用

1. 复制本目录下的 `_template.py` 为你自己的文件，例如 `my_studio_rules.py`
   （**不要**用下划线开头命名——下划线开头的文件会被加载器当作模板跳过）。
2. 在文件里定义你的 `Decoder` / `Validator`，并用 `register_profile(...)` 登记配置档。
3. 让系统发现它们：

   ```python
   from fbx_inspector import plugins
   plugins.discover()            # 加载内置示例 + 所有用户规则目录
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
