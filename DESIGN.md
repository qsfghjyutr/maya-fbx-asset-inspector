# 设计文档

`maya-fbx-asset-inspector` 是一套基于 Maya 2025 的工具链,用于检查游戏资产打包在**顶点色**和
**UV 通道**里的*计算数据*(切线空间法线、AO、风力遮罩、流向、bitmask……)。这些原始 float 对人
毫无可读性,而 Maya 自带的顶点色 / UV 编辑器也难以胜任。本工具把

```
通道(channel) → 解码(赋予语义) → 可视化 / 校验
```

做成一条**可插拔流水线**:一个稳定的小内核,加上各工作室按资产规范自行编写、随时替换的规则插件,
无需 fork。

## 指导性约束

- **Maya 2025** = Python **3.11** + **PySide6 / Qt6**(不是 PySide2)。网格数据通过
  `maya.api.OpenMaya`(API 2.0)访问。
- **FBX 通过导入 Maya 场景来检查**,再读取生成的网格。Maya 不把 FBX 当作数据格式直接读取。
  (用 FBX SDK 直连拿"真值"做交叉校验是后续路线图,不属于 v1。)
- **纯逻辑层保持与 Maya 无关**,以便脱离 DCC 做单元测试。凡是 import `maya.*` 或 PySide6 的代码,
  都在数据访问 / 可视化 / UI 边界内**惰性导入**。

## 数据模型,以及绝不能搞错的那一点

顶点色和 UV 集是**逐面顶点(face-vertex,即面角)**数据,而**不是**逐顶点。在硬边或 UV 缝处,同一个
网格顶点会有**多个**顶点色 / UV 值——每个相邻面角一个。若坍缩为逐顶点,就会在缝两侧静默地做平均,
从而同时破坏可视化和校验。

因此整条流水线的基本单位是**面顶点(face-vertex)**。每个解码后的数组都与一次面顶点遍历顺序逐元素对齐,
并在每个值旁携带其来源的 `face_id` 和 `vertex_id`,使得:

- 校验器能把问题精确定位到某个组件;
- 可视化器能把结果写回精确的那个面角。

逐顶点聚合(例如"显示平均值")是规则可以**主动请求**的一种归约,而非默认行为。

## 分层结构

```
fbx_inspector/
  core/       # 数据模型 + Maya 访问 + 插件注册表(注册表与 Maya 无关)
    types.py      DataKind, DecodedData            —— 与 Maya 无关
    channel.py    SourceType, Channel, ChannelData —— 与 Maya 无关
    mesh_data.py  MeshData(OpenMaya 读取)          —— 仅 Maya,惰性
    registry.py   插件注册表 + 装饰器               —— 与 Maya 无关
    context.py    InspectionContext(检查上下文)     —— 与 Maya 无关
  decode/     # ChannelData → DecodedData(语义 + 解包)              与 Maya 无关
  validate/   # DecodedData → [Issue]                              与 Maya 无关
  visualize/  # DecodedData → 视口表现
    colorset.py   标量 → 显示 color set(原生视口)   仅 Maya,惰性
    viewport.py   顶点数值文字 → VP2 DrawOverride                    仅 Maya,惰性
    viewport_plugin.py  数值标签 locator + MPxDrawOverride          仅 Maya
  rules/      # Rule / Profile:把通道绑定到角色,打包 解码+可视化+校验   与 Maya 无关
  presets/    # 内置默认 Profile;与 user_rules/_template.py 保持同一基准配置
  report.py   # RuleResult / Report,文本 + json                    与 Maya 无关
  api.py      # 高层编排入口
  ui/         # PySide6 浮动窗口 + 内嵌隔离视口                     仅 Maya,惰性
```

### 插件契约

三类插件,每类都是带稳定 `id` 的抽象基类(ABC),通过 `core.registry` 发现:

- **Decoder(解码器)**—— 把一个或多个具名的通道*角色*映射为有类型的 `DecodedData`
  (`SCALAR / VEC2 / VEC3 / VEC4 / MASK / ENUM`)。**解包**逻辑就住在这里(把一个 float 拆成两个
  8-bit 值、读取位域、重建法线的 z 分量等等)。
- **Visualizer(可视化器)**—— 声明自己 `accepts` 哪些 `DataKind`,把 `DecodedData` 转成视口表现,
  并能 `clear()` 掉自己添加的内容。标量 → color set 重映射;顶点数值文字 → DrawOverride。
- **Validator(校验器)**—— 把 `DecodedData` 转成一组 `Issue`(严重级别 + 消息 + 组件 id + 值)。
  内置:范围、NaN/Inf、vec3 归一化、常量/退化检查。

### 规则与配置档(定制的入口面)

一条 **Rule** 把具体的 `Channel` 绑定到某个解码器的角色名上,再把解码器与一个可选的可视化器、
一组校验器配对:

```python
Rule(
    id="ao_from_uv2",
    decoder=ScalarFromComponent(component="U"),
    channel_roles={"in": Channel(SourceType.UV_SET, "uvSet2")},
    visualizer=ColorSetRemapVisualizer(ramp="viridis"),
    validators=[RangeCheck(0.0, 1.0)],
)
```

一个 **Profile(检查预设)** 是一组带显示名称、说明和可选资产名匹配器的具名规则集合,因此工作室
可以把“我们的环境道具规范”作为一个对象整体交付。检查器会把内置默认 Profile 与用户登记的
Profile 放进预设下拉框,一键依次执行全部 Rule 并汇总报告。单条规则失败会被记录,不会阻断其余规则。

## 可视化策略(按数据类型分层)

- **标量 / 颜色** → 重映射进一个临时**显示 color set**,让 Maya 原生的"显示顶点色"来渲染。简单、
  稳健、无需自定义绘制代码。这是 v1 的主力。
- **数值文字** → 用 Viewport 2.0 的 **`MPxDrawOverride`**,通过 `MUIDrawManager` 在对应几何顶点旁
  绘制所选通道的数值,并支持调整字号。同一顶点的重复值去重;面顶点缝值以及空间重合但 vertex ID
  不同的顶点按位置合并,用 ` | ` 明确分隔,避免两个标签叠成一个误导性数字。
- **向量 / 方向** → 箭头可视化不属于 2.0,已推迟到未指定的后续版本。

## 曲线重映射(Ramp,chramp 式)

`core/remap.py` 的 `Ramp` 是一条 `[0,1] → [0,1]` 的曲线,由控制点 + 插值(线性/平滑/阶梯)
定义,用于在**可视化前**塑形数据——压暗、提亮、增强对比、聚焦某区间——而**不改动原始数据**
(校验仍针对原始值)。内置 `linear / quadratic / gamma / smoothstep / from_points` 预设。
`ColorSetRemapVisualizer` 接受可选 `curve=Ramp(...)`,在归一化之后、查色带之前施加。

## 用户规则与插件加载(与系统核心分离)

系统核心是 `fbx_inspector` 包,随版本更新;**用户自己的规则 .py 与配置表放在独立目录**,升级
系统不会覆盖它们。`plugins.py` 在运行时扫描并导入这些目录里的 .py(其内的注册调用即生效):

1. 环境变量 `FBX_INSPECTOR_RULE_PATH`(os.pathsep 分隔多目录);
2. 仓库根 `user_rules/`(你新增的文件是 git 未跟踪的,更新不动它);
3. 用户主目录 `~/.fbx_inspector/rules`。

文件名以下划线开头者被跳过(模板/私有)。`plugins.discover()` 默认先加载内置示例再加载用户目录;
检查器启动时使用 `include_examples=False`,另外显式注册 `presets/default.py`,因此正式预设列表
初始只有“默认”,随后追加用户 Profile。`user_rules/_template.py` 与默认预设采用相同规则结构,
复制并去掉文件名前导下划线即可创建新预设。

## 独立 GUI 检查窗口(嵌入隔离面板)

`ui/window.py` 的 `InspectorWindow`(PySide6 浮动窗口)提供一个**独立**的检查界面:既可像 UV
编辑器那样手动点 R/G/B/A 或 U/V,也可从“检查预设”中一键执行 Profile 的全部规则。预设生成的
各套 color set 都会保留,最后再重新应用执行前手动选中的通道,使当前画面立即刷新且不被最后一条
规则取代;底部仍显示完整预设报告。窗口还支持色带、归一化、`Ramp`、数值标签和坐标约定。

窗口中部内嵌一个**隔离的 Maya 视口**(`ui/viewport_panel.py` 的 `IsolatedMeshView`):复制目标网格
到远处的专属组,建专属相机与 `modelPanel`,用 `MQtUtil.findControl` + `wrapInstance` 把面板的 QWidget
取来内嵌,再用**每面板 `isolateSelect`** 让该面板只显示副本。着色写在**副本**的显示 color set 上,
因此**主视口 / 场景观感始终不变**。窗口关闭时清理副本、相机、面板。

这是"只读消费端"的又一形态:复用 `MeshData` → `ScalarFromComponent` → `ColorSetRemapVisualizer`
(`ui/channels.py::scalar_rule_for` 把三者按通道装配成 `Rule`),只是把着色目标从场景原物体换成了副本。
场景内可视化器(直接写原物体)作为"想在原生视口看"的另一选项保留。

约束:`modelPanel` 需要 GUI,无法用 mayapy 无头测;窗口只能在 Maya GUI 内手测。但"读原物体 → 着色副本
→ 原物体不受影响"这段数据链路可无头验证(见 `scripts/maya_smoke_test.py`)。

### 通用 Maya 插件可信加载桥

Inspector 本体是普通 Python 包:`install.py` 只需把仓库加入 `sys.path`,Shelf 点击时清除模块缓存,
便能直接读取仓库中的最新实现。数值标签不同:它使用 `MPxLocatorNode`、`MPxDrawOverride` 和
`MDrawRegistry`,必须经过 Maya 的 `cmds.loadPlugin()` / `MFnPlugin` 注册。Maya 会对所有
`loadPlugin()` 入口执行可信位置检查,直接加载仓库中的 `viewport_plugin.py` 会在新会话中触发
“不受信任位置”警告。

因此安装器只把根目录的通用桥 `fbx_inspector_plugin.py` 复制到 Maya 当前版本的用户 `plug-ins` 目录。
这个可信加载桥不包含功能代码,仅把 `initializePlugin` / `uninitializePlugin` 转发给仓库内的统一聚合
入口 `fbx_inspector.maya_plugin`。Viewport 以及未来新增的其他 Maya 插件模块都在聚合入口中登记,
始终复用同一个可信桥,不为每个模块复制单独的加载器。
Maya 每次启动并自动加载桥时都会读取仓库当时的最新版,因此更新功能代码后只需正常重启 Maya,无需
重新安装。Inspector 的普通 Python 模块仍会在每次点击 Shelf 时热重载。DrawOverride 已注册的 Python
类不在运行中强制卸载,因为 Maya 会警告这可能破坏稳定性与撤销队列。只有加载桥协议或仓库位置本身变化
时,才需要再次拖入 `install.py`。

### 坐标约定(Maya / 引擎)

隔离视口默认按 **Maya**(Y-up、右手)显示,可切换到目标引擎的坐标约定(v1 内置 **UE**:Z-up、左手),
让副本在窗口里呈现"导入引擎后应该是什么朝向"。`core/coord_convention.py`(与 Maya 无关、可单测)把每套
约定定义为一个 3x3 变换矩阵 + up 轴 / 手性等元数据;`ui/axis_indicator.py` 在视口**右上角**画一个固定小窗
的方向指示器(三色轴 X 红 / Y 绿 / Z 蓝),**随镜头 tumble 实时转动**并反映当前约定——类似 Blender/Unity 的
导航 gizmo(Maya 自带角落轴只会显示 Maya 世界,无法表达 UE 约定,故自绘)。投影数学(世界→相机旋转 +
约定 → 屏幕方向)是 Maya-free 纯函数可单测,只有 Qt 绘制 + 相机姿态查询需 GUI 手测。

指示器只变换箭头方向,标签与颜色始终绑定原本的 X/Y/Z 身份;不能在变换方向后再次按结果交换标签,
否则 UE 的 Y/Z 镜像会在视觉上被抵消。回归测试会按显示标签重建三轴并验证 UE 行列式小于 0。

关键正确性点:**Maya(右手)→ UE(左手)是换手性(镜像),不是纯旋转**——矩阵行列式为 -1,纯旋转做
不到。`CoordConvention.is_mirror` 由行列式推出(不手工维护),`IsolatedMeshView.set_coord_convention`
据此在切到镜像约定时对副本反转一次法线/绕序,补偿背面朝外。变换只作用在副本的 `content` 变换节点上,
与"藏到远处"的 `group` 平移职责分离,也**完全不触碰原始场景网格**、不影响按 face-vertex 索引写颜色的
逻辑。`MAYA_TO_UE` 矩阵集中放在一处常量,若与某项目的导出器设置(轴系统 / Force Front)不符只需改这一处。

## 路线图

1. **当前已落地** —— 逐面顶点读取、color set 重映射、内置解码器/校验器、DrawOverride 数值
   标签、隔离 GUI、多预设一键执行、Maya/UE 坐标预览、文本/json 报告。
2. 面向 CI 的批处理 / 无头校验,由 Profile 驱动。
3. 可选的 FBX SDK 直连解析,用于交叉校验 Maya 导入的保真度。

向量箭头(法线 / 流向)已从 2.0 移出,暂不绑定到 3.0 或其他具体版本。

## 测试

解码、校验、报告、注册表、规则装配都与 Maya 无关,用 `pytest` 脱离 DCC 覆盖。触及 Maya 的代码
(`mesh_data`、`visualize/*`、`ui/*`)基于 API 知识编写,**必须在 Maya 2025 内验证**;它们被设计为在
Maya 之外也能干净导入,从而让其余测试在任何环境都能跑。
