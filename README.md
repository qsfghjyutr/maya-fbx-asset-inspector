# maya-fbx-asset-inspector

*A Maya tool for inspecting FBX assets, including vertex colors, UVs, and customizable
visualization rules.*

*[English](#english) | [中文](#中文)*

---

## English

Game assets pack computed data into **vertex colors** and **UV channels** (tangent-space
normals, ambient occlusion, wind masks, flow directions, bitmasks, …). Those raw floats are
unreadable to a human, and Maya's stock vertex-color / UV editors can't visualize or validate
them well. This tool turns

```
channel → decode (give it meaning) → visualize / validate
```

into a **pluggable pipeline**: a small stable core plus rule plugins you author and swap per
asset convention — no forking required.

### Status

Version 0.1. The Maya-free layers are covered by the zero-dependency test suite. The Maya path
includes mesh reads, color-set visualization, a floating PySide6 inspector with an isolated
embedded viewport, preset-based batch inspection, Maya/UE coordinate previews, a handedness-aware
axis indicator, and numeric vertex labels through a Viewport 2.0 DrawOverride. `modelPanel` and
DrawOverride rendering still require final interactive verification in the Maya GUI. Vector-arrow
visualization remains deferred.

### Requirements

- **Maya 2025** (Python 3.11, PySide6 / Qt6) for the in-DCC features.
- `maya.api.OpenMaya`, `maya.cmds`, and PySide6 are provided by Maya — not installed via pip.

### Install (for use inside Maya)

**Drag `install.py` from a file browser into the Maya viewport** (or Maya menu File → Source
Script… → pick it). This creates an **FBXi** shelf button that opens the inspector, and registers
the repo on Maya's Python path via `userSetup.py` so it survives restarts — no typed paths, no
hardcoding (the location is derived from the file itself). The shelf button reloads the latest code
on each click, so editing source just needs a re-click. Installation also places one tiny, stable,
general-purpose `fbx_inspector_plugin.py` bridge in Maya's trusted per-user `plug-ins` directory.
This bridge contains no inspector implementation: it forwards all Maya plugin registration to the
current repository code, including future extension modules. It is necessary because
ordinary Inspector modules are imported through `sys.path`, while `MPxDrawOverride` must be
registered through `loadPlugin()`, which applies Maya's trusted-location security check. Uninstall:
`import install; install.uninstall()`. The bridge reads the latest repository implementation on
each Maya startup; Viewport plugin changes therefore require a Maya restart, not reinstallation.

For off-DCC development: `pip install -e ".[dev]"`.

### Quick start (out-of-box example)

An example ships ready to run — visualize each vertex-color channel separately as a heatmap:

```python
import maya.cmds as cmds
from fbx_inspector.api import run_profile, clear_visualizations
from fbx_inspector.examples.vertex_color_channels import vertex_color_channels_profile

mesh = cmds.ls(selection=True)[0]
profile = vertex_color_channels_profile("colorSet1")   # your color set name
run_profile(mesh, profile)   # writes __inspector___R/_G/_B/_A color sets; switch current set to view each
# clear_visualizations(mesh, profile)
```

Shape the display with a **Ramp** curve (chramp-style 0-1 → 0-1 remap; `quadratic`, `gamma`,
`smoothstep`, or custom points) without altering the raw data:

```python
from fbx_inspector.core.remap import Ramp
from fbx_inspector.examples.vertex_color_channels import channel_view_rule
rule = channel_view_rule("colorSet1", "R", curve=Ramp.quadratic())
```

### Inspector window (dedicated GUI)

Open a separate floating window that visualizes each channel in its **own isolated viewport** — the
main Maya viewport and scene stay unchanged. Select a mesh, then:

```python
from fbx_inspector.ui import open_inspector
open_inspector()          # or open_inspector("meshName")
```

Click R/G/B/A to view color-set components, U/V for UV sets; adjust ramp / normalize / curve. Enable
numeric values to label the corresponding vertices and adjust their font size. Repeated values are
deduplicated; distinct values belonging to the same or coincident vertices use an explicit
separator such as `1 | 0.01`, avoiding ambiguous overdraw. The window shows a temporary offset
duplicate in its embedded panel and removes it when closed.

LOD assets can be opened by selecting either one LOD mesh or their parent group. Name the mesh
transforms with a shared prefix and an `_LOD<number>` or `-LOD<number>` suffix, for example
`Tree_LOD0`, `Tree_LOD1`, and `Tree_LOD2`. The inspector discovers the set and exposes a
LOD slider; a single mesh without such a suffix is treated as LOD0. Moving the slider replaces
only the isolated preview duplicate and refreshes the current channel data. Camera tumble, pan,
zoom, coordinate convention, visualization options, and same-named Color/UV Set selections are
preserved. A channel selection falls back only when that channel is absent from the target LOD.

The **Inspection preset** selector runs every Rule in a Profile with one click and combines their
results into one report. The built-in **Default** preset checks `colorSet1` R/G/B/A against [0, 1]
and creates four grayscale display color sets. After batch execution, the channel that was being
viewed manually is refreshed and restored instead of leaving the viewport on the preset's last
rule.

### Your own rules (never overwritten by updates)

Put your rule `.py` files and config tables in a folder **separate** from the core package, so
system updates don't touch them: set `FBX_INSPECTOR_RULE_PATH`, or use the repo's `user_rules/`,
or `~/.fbx_inspector/rules`. Copy `user_rules/_template.py` to a filename that does not start with
`_`, edit its Profile, and reopen the inspector from the shelf. Registered Profiles appear
automatically in the preset selector; no core-package edits are required. Direct calls to
`plugins.discover()` still load shipped examples plus user rules, while the production inspector
intentionally lists the built-in default and user Profiles only.

### Project structure

The tree below covers only maintained project files that are version-controlled or intended for
the current change.

```text
maya-fbx-asset-inspector/
├─ fbx_inspector/                    Main Python package
│  ├─ __init__.py                    Package metadata; safe to import outside Maya
│  ├─ api.py                         Public run_profile / clear_visualizations API
│  ├─ plugins.py                     Discovers built-in examples and user rule files
│  ├─ report.py                      Text/JSON inspection report assembly
│  ├─ maya_plugin.py                 Aggregates Maya plugin registration entry points
│  ├─ core/                          Shared data model and infrastructure
│  │  ├─ __init__.py                 Core package marker
│  │  ├─ channel.py                  Channel types and face-vertex channel data
│  │  ├─ context.py                  Options shared by one inspection run
│  │  ├─ coord_convention.py         Maya/UE axes, handedness, matrices, and UV-V conversion
│  │  ├─ mesh_data.py                Maya API mesh and color/UV-set access
│  │  ├─ registry.py                 Decoder, visualizer, validator, and Profile registries
│  │  ├─ remap.py                    Ramp curves and interpolation presets
│  │  └─ types.py                    Decoded values, issues, results, and visualization metadata
│  ├─ decode/                        Raw-channel decoding
│  │  ├─ __init__.py                 Decoder package exports
│  │  ├─ base.py                     Decoder base class and input-role validation
│  │  └─ builtin.py                  Scalar, vector, and packed-value decoders
│  ├─ validate/                      Decoded-data checks
│  │  ├─ __init__.py                 Validator package exports
│  │  ├─ base.py                     Validator interface
│  │  └─ builtin.py                  Range, finite, normalized, and constant checks
│  ├─ visualize/                     Viewport output implementations
│  │  ├─ __init__.py                 Visualizer package exports
│  │  ├─ base.py                     Visualizer base class, ramps, and clamp helpers
│  │  ├─ colorset.py                 Scalar-to-color-set heatmap visualization
│  │  ├─ viewport.py                 Numeric-label formatting, grouping, and node payloads
│  │  └─ viewport_plugin.py          VP2 locator and MPxDrawOverride text drawing
│  ├─ rules/                         Rule and Profile composition
│  │  ├─ __init__.py                 Rules package marker
│  │  └─ profile.py                  Rule execution and named multi-rule Profile presets
│  ├─ presets/                       Production presets shown by the inspector
│  │  ├─ __init__.py                 Preset package exports
│  │  └─ default.py                  Built-in colorSet1 RGBA default preset
│  ├─ examples/                      Programmatic API examples, not production UI presets
│  │  ├─ __init__.py                 Registers shipped examples when imported
│  │  └─ vertex_color_channels.py    Per-channel vertex-color Profile example
│  └─ ui/                            Maya/PySide inspector interface
│     ├─ __init__.py                 Lazy open_inspector export
│     ├─ axis_indicator.py           Camera-following Maya/UE handedness indicator
│     ├─ channels.py                 Manual channel-selection Rule factory
│     ├─ lod.py                      LOD name parsing and Maya DAG discovery
│     ├─ viewport_panel.py           Isolated duplicate, camera, and embedded modelPanel
│     └─ window.py                   Floating window, preset runner, controls, and report pane
├─ user_rules/                       User-owned preset and rule area
│  ├─ _template.py                   Copyable preset matching the built-in default
│  └─ README.md                      User preset authoring and discovery instructions
├─ scripts/                          Development and Maya verification helpers
│  ├─ maya_smoke_test.py             Headless mayapy integration smoke test
│  └─ reload_dev.py                  Removes cached modules during Maya development
├─ tests/                            Maya-free automated test suite
│  ├─ __init__.py                    Test package marker
│  ├─ conftest.py                    Test import-path/bootstrap setup
│  ├─ test_axis_indicator.py         Axis projection and UE handedness regressions
│  ├─ test_channels.py               Manual channel Rule factory tests
│  ├─ test_context.py                Inspection-context default tests
│  ├─ test_coord_convention.py       Coordinate and UV conversion tests
│  ├─ test_decode.py                 Built-in decoder tests
│  ├─ test_examples.py               Shipped example Profile tests
│  ├─ test_lod.py                    LOD naming parser tests
│  ├─ test_plugins.py                User rule discovery/loading tests
│  ├─ test_presets.py                Default preset registration tests
│  ├─ test_remap.py                  Ramp curve tests
│  ├─ test_rules.py                  Rule/Profile execution and report tests
│  ├─ test_validate.py               Built-in validator tests
│  └─ test_viewport_text.py          Numeric formatting and coincident-label tests
├─ fbx_inspector_plugin.py           Trusted Maya plug-in bridge installed per user
├─ install.py                        Drag-and-drop Maya installer and uninstaller
├─ run_tests.py                      Zero-dependency test runner
├─ pyproject.toml                    Packaging, Python, pytest, Ruff, and mypy configuration
├─ README.md                         User-facing English/Chinese guide
├─ DESIGN.md                         Architecture, invariants, and implementation decisions
├─ LICENSE                           Project license
├─ .editorconfig                     Cross-editor whitespace conventions
├─ .gitattributes                    Git text and attribute rules
└─ .gitignore                        Files excluded from version control
```

### Concepts

- **Decoder** — turns raw channel components into typed data (scalar / vec2/3/4 / mask / enum),
  including unpacking (e.g. two 8-bit values in one float).
- **Visualizer** — renders decoded data. Scalars remap into a display color set (native viewport);
  numeric vertex labels use a Viewport 2.0 DrawOverride. Vector arrows are deferred.
- **Validator** — checks decoded data (range, NaN/Inf, normalized, constant) and reports
  issues located at exact face-vertices.
- **Rule / Profile** — a Rule binds channels to a decoder and pairs it with a visualizer +
  validators; a Profile is a named, described preset with an optional asset-name matcher and any
  number of Rules.

The pipeline's unit is the **face-vertex**, so hard edges and UV seams are handled correctly
rather than averaged away. See [DESIGN.md](DESIGN.md).

### Testing

Three layers:

1. **Pure logic** (decode / validate / Ramp / rules / plugins), no Maya needed — runs on any
   Python 3.11+:

   ```bash
   python run_tests.py        # zero-dependency runner (works offline)
   pytest                     # same tests, if pytest is installed
   ```

2. **Maya end-to-end** (mesh reads + color-set writes + example + curve), headless via `mayapy`:

   ```bash
   "/d/Program Files (x86)/Autodesk/Maya2025/bin/mayapy.exe" scripts/maya_smoke_test.py
   ```

   Each run is a fresh process, so it always reflects the latest source (ideal for regression).

3. **Interactive** in the Maya GUI — select a mesh, `open_inspector()`, click through channels;
   confirm the embedded panel recolors while the **main viewport stays unchanged**, and that
   closing the window removes the `__fbx_inspector_grp__` duplicate.

> **Developing in Maya — reload after editing source.** Maya's Python session is persistent, so a
> re-`import` returns the *cached* old module and your edits won't take effect (you may see errors
> like `unexpected keyword argument`). After editing source, either restart Maya, or purge the
> cached modules first:
>
> ```python
> from scripts.reload_dev import reload_fbx_inspector
> reload_fbx_inspector()     # drops fbx_inspector.* from sys.modules; re-import afterwards
> ```
>
> The headless `mayapy` smoke test is immune to this (new process each run).

---

## 中文

游戏资产会把计算数据打包进**顶点色**和 **UV 通道**(切线空间法线、AO、风力遮罩、流向、
bitmask……)。这些原始 float 对人毫无可读性,Maya 自带的顶点色 / UV 编辑器也难以对其做可视化与
校验。本工具把

```
通道 → 解码(赋予语义) → 可视化 / 校验
```

做成一条**可插拔流水线**:一个稳定的小内核,加上你按资产规范自行编写、随时替换的规则插件,无需
fork。

### 现状

当前版本为 v0.1。与 Maya 无关的各层由零依赖测试覆盖。Maya 链路现已包括网格读取、color set
可视化、带隔离视口的 PySide6 浮动窗口、多预设一键检查、Maya/UE 坐标预览、能正确表达手性的
方向指示器，以及基于 Viewport 2.0 DrawOverride 的顶点数值标签。`modelPanel` 与 DrawOverride
的最终绘制效果仍需在 Maya GUI 中交互验证。向量箭头可视化仍留待后续版本。

### 环境要求

- **Maya 2025**(Python 3.11,PySide6 / Qt6)用于 DCC 内功能。
- `maya.api.OpenMaya`、`maya.cmds`、PySide6 由 Maya 提供,不通过 pip 安装。

### 安装(在 Maya 内使用)

**把 `install.py` 从资源管理器拖进 Maya 视口**(或 Maya 菜单 File → Source Script… 选中它)。这会
创建一个 **FBXi** 工具架按钮用于打开检查器,并通过 `userSetup.py` 把仓库注册到 Maya 的 Python
路径上,重启后依然可用——无需输入路径、无硬编码(位置由文件自身推导)。按钮每次点击都会重载最新
代码,所以改完源码再点一下即可。安装时还会在 Maya 当前版本的用户 `plug-ins` 目录放置唯一一个很小且
稳定的通用桥 `fbx_inspector_plugin.py`。它不包含 Inspector 功能实现,只把所有 Maya 插件注册转发到
仓库中的统一入口;未来新增插件模块也复用这一个桥,无需复制新的加载器。
之所以必须有这层桥,是因为 Inspector 本体作为普通 Python 包通过 `sys.path` 导入,不经过 Maya 插件
安全检查;而 `MPxDrawOverride` 必须通过 `loadPlugin()` 注册,Maya 会对入口文件执行可信位置检查。
加载桥会在每次 Maya 启动时读取仓库最新版,所以 Viewport 插件代码更新后只需重启 Maya,无需重新安装。
卸载:`import install; install.uninstall()`。

脱离 DCC 开发时:`pip install -e ".[dev]"`。

### 快速上手(开箱即用示例)

内置一个可直接运行的示例——把顶点色的每个分量分别渲染成热力图:

```python
import maya.cmds as cmds
from fbx_inspector.api import run_profile, clear_visualizations
from fbx_inspector.examples.vertex_color_channels import vertex_color_channels_profile

mesh = cmds.ls(selection=True)[0]
profile = vertex_color_channels_profile("colorSet1")   # 换成你的 color set 名
run_profile(mesh, profile)   # 写入 __inspector___R/_G/_B/_A;切换 current color set 逐路查看
# clear_visualizations(mesh, profile)
```

用 **Ramp** 曲线(chramp 式 0-1→0-1 重映射;`quadratic` / `gamma` / `smoothstep` / 自定义点)
塑形显示,而不改动原始数据:

```python
from fbx_inspector.core.remap import Ramp
from fbx_inspector.examples.vertex_color_channels import channel_view_rule
rule = channel_view_rule("colorSet1", "R", curve=Ramp.quadratic())
```

### 检查窗口(独立 GUI)

打开一个独立的浮动窗口,每个通道在它**自己的隔离视口**里显示——主 Maya 视口和场景保持不变。
选中网格后:

```python
from fbx_inspector.ui import open_inspector
open_inspector()          # 或 open_inspector("网格名")
```

点 R/G/B/A 看 color set 分量,U/V 看 UV set;可调色带 / 归一化 / 曲线。窗口在其内嵌面板里显示一份
偏移到远处的临时副本,关闭时自动移除。开启“显示数值”后,所选通道的数值会标在对应顶点旁,
字号可调;重复值会去重,同一顶点或空间重合顶点的不同值用 `1 | 0.01` 这样的明确分隔符合并,
避免文字重叠成 `10.01`。

LOD 资产既可以选中其中一个 LOD 网格打开,也可以选中包含全部 LOD 的父组。网格 transform 需使用
相同前缀及 `_LOD<序号>` 或 `-LOD<序号>` 后缀,例如 `Tree_LOD0`、`Tree_LOD1`、
`Tree_LOD2`。检查器会自动发现整组并显示 LOD 滑动条;没有此后缀的单个网格按 LOD0 处理。
拖动滑动条只替换隔离预览副本并刷新当前通道数据,相机旋转/平移/缩放、坐标系、可视化选项及
同名 Color/UV Set 选择均保持不变。只有目标 LOD 缺少当前通道时才会回退到可用通道。

“检查预设”下拉框可以一键执行一个 Profile 中的全部 Rule,并把结果合并成一份报告。内置
“默认”预设检查 `colorSet1` 的 R/G/B/A 是否位于 [0,1],同时生成四套灰度显示 color set。
批量执行结束后会自动刷新并恢复执行前手动查看的通道,不会停留在最后一条预设规则上。

### 你自己的规则(系统更新不覆盖)

把规则 `.py` 与配置表放在**独立于核心包**的目录,系统升级不会动它们:设置环境变量
`FBX_INSPECTOR_RULE_PATH`,或用仓库的 `user_rules/`,或 `~/.fbx_inspector/rules`。复制
`user_rules/_template.py` 并改成不以下划线开头的文件名,编辑并登记 Profile,再从工具架重开
检查器;用户预设会自动出现在下拉框中,无需修改核心包。直接调用 `plugins.discover()` 仍会加载
内置示例和用户规则;正式检查器只列出内置默认预设与用户 Profile。

### 项目结构

下面只列出受版本控制或将在当前变更中纳入版本控制的项目文件。

```text
maya-fbx-asset-inspector/
├─ fbx_inspector/                    主 Python 包
│  ├─ __init__.py                    包元数据;可在 Maya 外安全导入
│  ├─ api.py                         run_profile / clear_visualizations 公共 API
│  ├─ plugins.py                     发现内置示例与用户规则文件
│  ├─ report.py                      组装文本和 JSON 检查报告
│  ├─ maya_plugin.py                 汇总 Maya 插件注册入口
│  ├─ core/                          共享数据模型与基础设施
│  │  ├─ __init__.py                 core 包标记
│  │  ├─ channel.py                  通道类型与逐面顶点通道数据
│  │  ├─ context.py                  单次检查共享选项
│  │  ├─ coord_convention.py         Maya/UE 轴、手性、矩阵与 UV-V 转换
│  │  ├─ mesh_data.py                Maya API 网格及 color/UV set 访问
│  │  ├─ registry.py                 Decoder、Visualizer、Validator、Profile 注册表
│  │  ├─ remap.py                    Ramp 曲线与插值预设
│  │  └─ types.py                    解码数据、问题、结果和可视化元数据
│  ├─ decode/                        原始通道解码
│  │  ├─ __init__.py                 Decoder 包导出
│  │  ├─ base.py                     Decoder 基类与输入角色校验
│  │  └─ builtin.py                  标量、向量和打包数值解码器
│  ├─ validate/                      解码数据校验
│  │  ├─ __init__.py                 Validator 包导出
│  │  ├─ base.py                     Validator 接口
│  │  └─ builtin.py                  范围、有限值、归一化和常量检查
│  ├─ visualize/                     视口输出实现
│  │  ├─ __init__.py                 Visualizer 包导出
│  │  ├─ base.py                     Visualizer 基类、色带和 clamp 工具
│  │  ├─ colorset.py                 标量到 color set 热力图可视化
│  │  ├─ viewport.py                 数值标签格式、重合合并与节点载荷
│  │  └─ viewport_plugin.py          VP2 locator 与 MPxDrawOverride 文字绘制
│  ├─ rules/                         Rule 与 Profile 组合
│  │  ├─ __init__.py                 rules 包标记
│  │  └─ profile.py                  Rule 执行和具名多规则 Profile 预设
│  ├─ presets/                       检查器显示的正式预设
│  │  ├─ __init__.py                 预设包导出
│  │  └─ default.py                  内置 colorSet1 RGBA 默认预设
│  ├─ examples/                      编程 API 示例,不进入正式 UI 预设列表
│  │  ├─ __init__.py                 导入时登记随附示例
│  │  └─ vertex_color_channels.py    逐通道顶点色 Profile 示例
│  └─ ui/                            Maya/PySide 检查器界面
│     ├─ __init__.py                 惰性导出 open_inspector
│     ├─ axis_indicator.py           随相机转动的 Maya/UE 手性指示器
│     ├─ channels.py                 手动选择通道的 Rule 工厂
│     ├─ lod.py                      LOD 名称解析与 Maya DAG 发现
│     ├─ viewport_panel.py           隔离副本、相机与内嵌 modelPanel
│     └─ window.py                   浮动窗口、预设执行、控件与报告区
├─ user_rules/                       用户拥有的预设与规则目录
│  ├─ _template.py                   与内置默认配置一致的可复制模板
│  └─ README.md                      用户预设编写与发现说明
├─ scripts/                          开发及 Maya 验证工具
│  ├─ maya_smoke_test.py             mayapy 无头集成冒烟测试
│  └─ reload_dev.py                  Maya 开发时移除缓存模块
├─ tests/                            不依赖 Maya 的自动化测试
│  ├─ __init__.py                    测试包标记
│  ├─ conftest.py                    测试导入路径与启动配置
│  ├─ test_axis_indicator.py         坐标轴投影及 UE 手性回归测试
│  ├─ test_channels.py               手动通道 Rule 工厂测试
│  ├─ test_context.py                检查上下文默认值测试
│  ├─ test_coord_convention.py       坐标及 UV 转换测试
│  ├─ test_decode.py                 内置 Decoder 测试
│  ├─ test_examples.py               随附示例 Profile 测试
│  ├─ test_lod.py                    LOD 命名解析测试
│  ├─ test_plugins.py                用户规则发现与加载测试
│  ├─ test_presets.py                默认预设注册测试
│  ├─ test_remap.py                  Ramp 曲线测试
│  ├─ test_rules.py                  Rule/Profile 执行与报告测试
│  ├─ test_validate.py               内置 Validator 测试
│  └─ test_viewport_text.py          数值格式和重合标签测试
├─ fbx_inspector_plugin.py           安装到用户目录的可信 Maya 插件桥
├─ install.py                        Maya 拖拽安装器与卸载器
├─ run_tests.py                      零依赖测试运行器
├─ pyproject.toml                    打包、Python、pytest、Ruff、mypy 配置
├─ README.md                         面向用户的中英文说明
├─ DESIGN.md                         架构、不变量与实现决策
├─ LICENSE                           项目许可证
├─ .editorconfig                     跨编辑器空白约定
├─ .gitattributes                    Git 文本及属性规则
└─ .gitignore                        版本控制排除规则
```

### 核心概念

- **Decoder(解码器)**—— 把原始通道分量解释为有类型的数据(标量 / vec2/3/4 / mask / enum),
  含解包(如一个 float 里的两个 8-bit 值)。
- **Visualizer(可视化器)**—— 渲染解码后的数据。标量重映射进显示 color set(原生视口);
  顶点数值标签走 Viewport 2.0 DrawOverride。向量箭头已推迟。
- **Validator(校验器)**—— 校验解码数据(范围、NaN/Inf、归一化、常量),并把问题精确定位到
  面顶点。
- **Rule / Profile(规则 / 预设)**—— Rule 把通道绑定到解码器,再配可视化器 + 校验器;
  Profile 带显示名称、说明和可选资产名匹配器,按工作室规范打包任意数量的规则。

流水线的基本单位是**面顶点(face-vertex)**,因此硬边与 UV 缝会被正确处理,而非被平均掉。
详见 [DESIGN.md](DESIGN.md)。

### 测试

三层:

1. **纯逻辑**(解码 / 校验 / Ramp / 规则 / 插件),无需 Maya,任意 Python 3.11+ 可跑:

   ```bash
   python run_tests.py        # 零依赖运行器(离线可用)
   pytest                     # 装了 pytest 的话,同样的测试
   ```

2. **Maya 端到端**(网格读取 + color set 写回 + 示例 + 曲线),用 `mayapy` 无头运行:

   ```bash
   "/d/Program Files (x86)/Autodesk/Maya2025/bin/mayapy.exe" scripts/maya_smoke_test.py
   ```

   每次都是全新进程,总是反映最新源码(适合做回归)。

3. **交互式**(Maya GUI)——选中网格,`open_inspector()`,逐个点通道;确认内嵌面板随之变色而
   **主视口毫无变化**,且关闭窗口后 `__fbx_inspector_grp__` 副本被移除。

> **在 Maya 内开发——改完源码要重载。** Maya 的 Python 会话是常驻的,重新 `import` 只会拿到
> *缓存的旧模块*,你的改动不生效(可能报 `unexpected keyword argument` 之类的错)。改完源码后,
> 要么重启 Maya,要么先清掉缓存模块:
>
> ```python
> from scripts.reload_dev import reload_fbx_inspector
> reload_fbx_inspector()     # 从 sys.modules 移除 fbx_inspector.*,之后重新 import
> ```
>
> 无头的 `mayapy` 冒烟测试不受此影响(每次都是新进程)。
