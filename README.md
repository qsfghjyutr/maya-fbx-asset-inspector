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

Version 0.1. The Maya-free layers (decode / validate / rules / report / registry) are implemented
and unit-tested. The core Maya path (mesh reads + color-set visualizer) has been verified in Maya
2025 via `scripts/maya_smoke_test.py`. The PySide6 inspector window, isolated embedded viewport,
coordinate-convention preview, and axis indicator are implemented; because `modelPanel` requires a
Maya GUI, those UI paths require interactive testing. Version 2.0 development adds numeric labels
beside vertices through a Viewport 2.0 DrawOverride, with adjustable font size. Vector-arrow
visualization is deferred to an unspecified later release.

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
numeric values to label the corresponding vertices and adjust their font size. Repeated
face-vertex values are collapsed per vertex; distinct seam values are shown on separate lines. The
window shows a temporary offset duplicate in its embedded panel and removes it when closed.

### Your own rules (never overwritten by updates)

Put your rule `.py` files and config tables in a folder **separate** from the core package, so
system updates don't touch them: set `FBX_INSPECTOR_RULE_PATH`, or use the repo's `user_rules/`,
or `~/.fbx_inspector/rules`. Then `fbx_inspector.plugins.discover()` loads examples + your rules.
Copy `user_rules/_template.py` to get started.

### Concepts

- **Decoder** — turns raw channel components into typed data (scalar / vec2/3/4 / mask / enum),
  including unpacking (e.g. two 8-bit values in one float).
- **Visualizer** — renders decoded data. Scalars remap into a display color set (native viewport);
  numeric vertex labels use a Viewport 2.0 DrawOverride. Vector arrows are deferred.
- **Validator** — checks decoded data (range, NaN/Inf, normalized, constant) and reports
  issues located at exact face-vertices.
- **Rule / Profile** — a Rule binds channels to a decoder and pairs it with a visualizer +
  validators; a Profile bundles rules for a studio's asset convention.

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

当前版本为 v0.1。与 Maya 无关的各层(解码 / 校验 / 规则 / 报告 / 注册表)已实现并有单元测试。
核心 Maya 链路(网格读取 + color set 可视化)已通过 `scripts/maya_smoke_test.py` 在 Maya 2025
内验证。PySide6 检查窗口、内嵌隔离视口、坐标约定预览和方向指示器均已实现;由于
`modelPanel` 依赖 Maya GUI,这些 UI 链路仍需交互式测试。2.0 开始加入基于 Viewport 2.0
DrawOverride 的顶点旁数值标签,并支持调整字号。向量箭头可视化已推迟到未指定的后续版本。

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
字号可调;同一顶点的重复值会合并,缝两侧的不同值则分行显示。

### 你自己的规则(系统更新不覆盖)

把规则 `.py` 与配置表放在**独立于核心包**的目录,系统升级不会动它们:设置环境变量
`FBX_INSPECTOR_RULE_PATH`,或用仓库的 `user_rules/`,或 `~/.fbx_inspector/rules`。随后
`fbx_inspector.plugins.discover()` 会加载示例 + 你的规则。复制 `user_rules/_template.py` 起步。

### 核心概念

- **Decoder(解码器)**—— 把原始通道分量解释为有类型的数据(标量 / vec2/3/4 / mask / enum),
  含解包(如一个 float 里的两个 8-bit 值)。
- **Visualizer(可视化器)**—— 渲染解码后的数据。标量重映射进显示 color set(原生视口);
  顶点数值标签走 Viewport 2.0 DrawOverride。向量箭头已推迟。
- **Validator(校验器)**—— 校验解码数据(范围、NaN/Inf、归一化、常量),并把问题精确定位到
  面顶点。
- **Rule / Profile(规则 / 配置档)**—— Rule 把通道绑定到解码器,再配可视化器 + 校验器;
  Profile 按工作室资产规范打包一组规则。

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
