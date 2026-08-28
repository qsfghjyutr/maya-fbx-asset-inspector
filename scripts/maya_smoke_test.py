"""在 Maya 内(通过 mayapy)对最高风险链路做端到端冒烟测试。

验证内容:
  1. core.mesh_data.MeshData 逐面顶点读取 color set / UV set;
  2. 一条完整规则:解码 → 校验 → color set 重映射可视化;
  3. 可视化 color set 的写入与清理。

运行(Git Bash):
  "/d/Program Files (x86)/Autodesk/Maya2025/bin/mayapy.exe" scripts/maya_smoke_test.py

在 Maya 的 Script Editor 里,则先把仓库根目录加入 sys.path 再执行本文件的主体。
"""

from __future__ import annotations

import os
import sys

# 让 mayapy 能找到 fbx_inspector(仓库根目录)。
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def main() -> int:
    import maya.standalone

    maya.standalone.initialize()  # 无头模式初始化 Maya

    import maya.cmds as cmds

    from fbx_inspector.api import clear_visualizations, run_profile
    from fbx_inspector.core.channel import Channel, SourceType
    from fbx_inspector.core.context import InspectionContext
    from fbx_inspector.core.mesh_data import MeshData
    from fbx_inspector.decode.builtin import ScalarFromComponent
    from fbx_inspector.rules.profile import Profile, Rule
    from fbx_inspector.validate.builtin import RangeCheck
    from fbx_inspector.visualize.colorset import ColorSetRemapVisualizer

    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        print(("  OK  " if cond else " FAIL ") + msg)
        if not cond:
            failures.append(msg)

    # —— 造一个测试网格:20 段球体 + 一个 color set,R 通道写入 [0,1] 渐变 ——
    cmds.file(new=True, force=True)
    sphere = cmds.polySphere(subdivisionsX=20, subdivisionsY=20, name="smokeSphere")[0]
    cmds.polyColorSet(sphere, create=True, colorSet="testColor", representation="RGBA")
    cmds.polyColorSet(sphere, currentColorSet=True, colorSet="testColor")
    # 按顶点索引给一个可预测的渐变(R = i / n),顺便留一个越界值探测 RangeCheck。
    verts = cmds.polyEvaluate(sphere, vertex=True)
    for i in range(verts):
        r = i / float(verts - 1)
        cmds.polyColorPerVertex(f"{sphere}.vtx[{i}]", rgb=(r, 0.0, 0.0))
    cmds.polyColorPerVertex(f"{sphere}.vtx[0]", rgb=(2.0, 0.0, 0.0))  # 故意越界

    print("\n[1] MeshData 读取")
    mesh = MeshData(sphere)
    color_channel = Channel(SourceType.COLOR_SET, "testColor")
    cd = mesh.read_channel(color_channel)
    check("testColor" in mesh.color_set_names(), "枚举到 color set: testColor")
    check("map1" in mesh.uv_set_names(), "枚举到默认 UV set: map1")
    check(len(cd) > 0, f"读到面顶点数据(face-vertex 计数 = {len(cd)})")
    check(len(cd.vertex_ids) == len(cd) == len(cd.face_ids), "分量/顶点/面 id 逐元素对齐")
    check(set("RGBA").issubset(cd.components), "color set 读出 RGBA 四分量")

    print("\n[2] UV set 读取")
    uv_cd = mesh.read_channel(Channel(SourceType.UV_SET, "map1"))
    check(len(uv_cd) == len(cd), "UV 读取的面顶点数与 color set 一致")
    check(set("UV").issubset(uv_cd.components), "UV set 读出 U/V 两分量")

    print("\n[3] 规则:解码 R → 范围校验 → color set 可视化")
    rule = Rule(
        id="r_channel_check",
        decoder=ScalarFromComponent(component="R"),
        channel_roles={"in": color_channel},
        visualizer=ColorSetRemapVisualizer(ramp="viridis", normalize=True),
        validators=[RangeCheck(0.0, 1.0)],
    )
    profile = Profile(id="smoke", rules=[rule])

    # 先只校验,不改场景。
    report = run_profile(sphere, profile, validate_only=True)
    check(report.total_errors >= 1, f"RangeCheck 抓到越界值(errors = {report.total_errors})")

    # 再完整跑一遍(含可视化写入)。
    ctx = InspectionContext(mesh_name=sphere)
    viz_set = f"{ctx.visualize_prefix}_remap"
    report2 = run_profile(sphere, profile)
    all_sets = cmds.polyColorSet(sphere, query=True, allColorSets=True) or []
    check(report2.results[0].visualized, "规则报告标记 visualized=True")
    info = report2.results[0].viz_info
    check(
        info is not None and info.normalized and info.data_min is not None,
        f"可视化回传归一化区间: min={getattr(info, 'data_min', None)}, "
        f"max={getattr(info, 'data_max', None)}",
    )
    check("归一化区间" in report2.to_text(), "文本报告显示归一化 min/max")
    check(viz_set in all_sets, f"可视化 color set 已写入: {viz_set}")
    check(cmds.getAttr(f"{sphere}.displayColors") == 1, "已打开 displayColors")

    print("\n[4] 清理可视化")
    clear_visualizations(sphere, profile)
    all_sets_after = cmds.polyColorSet(sphere, query=True, allColorSets=True) or []
    check(viz_set not in all_sets_after, "可视化 color set 已被清理")

    print("\n[5] 示例规则:分通道可视化 + 二次曲线重映射")
    from fbx_inspector.core.remap import Ramp
    from fbx_inspector.examples.vertex_color_channels import (
        channel_view_rule,
        vertex_color_channels_profile,
    )

    ex_profile = vertex_color_channels_profile("testColor")
    run_profile(sphere, ex_profile)
    sets_after_ex = cmds.polyColorSet(sphere, query=True, allColorSets=True) or []
    per_channel = [f"{ctx.visualize_prefix}_{c}" for c in ("R", "G", "B", "A")]
    check(
        all(s in sets_after_ex for s in per_channel),
        f"分通道各写独立 color set: {per_channel}",
    )
    clear_visualizations(sphere, ex_profile)

    curved = Rule(
        id="r_quadratic",
        decoder=ScalarFromComponent(component="R"),
        channel_roles={"in": color_channel},
        visualizer=ColorSetRemapVisualizer(curve=Ramp.quadratic(), set_suffix="R_q"),
    )
    run_profile(sphere, Profile(id="q", rules=[curved]))
    sets_q = cmds.polyColorSet(sphere, query=True, allColorSets=True) or []
    check(f"{ctx.visualize_prefix}_R_q" in sets_q, "二次曲线可视化写入 color set")
    clear_visualizations(sphere, Profile(id="q", rules=[curved]))

    print("\n[6] 独立窗口链路(无头):副本着色,原物体不受影响")
    from fbx_inspector.core.channel import SourceType
    from fbx_inspector.ui.channels import scalar_rule_for
    from fbx_inspector.ui.viewport_panel import VIEW_SET_SUFFIX

    orig_sets_before = set(cmds.polyColorSet(sphere, query=True, allColorSets=True) or [])
    orig_dc_before = cmds.getAttr(f"{sphere}.displayColors")

    dup = cmds.duplicate(sphere, name="__smoke_dup__", returnRootsOnly=True)[0]
    rule = scalar_rule_for(
        SourceType.COLOR_SET, "testColor", "R", set_suffix=VIEW_SET_SUFFIX
    )
    # 复现 IsolatedMeshView.show_channel 的着色部分(不建 modelPanel,故可无头跑)
    src_view = MeshData(sphere)
    dup_view = MeshData(dup)
    ch_data = {r: src_view.read_channel(c) for r, c in rule.channel_roles.items()}
    decoded = rule.decoder.decode(ch_data)
    rule.visualizer.apply(dup_view, decoded, InspectionContext(mesh_name=dup))

    dup_sets = cmds.polyColorSet(dup, query=True, allColorSets=True) or []
    check(f"__inspector___{VIEW_SET_SUFFIX}" in dup_sets, "副本写入了显示 color set")

    orig_sets_after = set(cmds.polyColorSet(sphere, query=True, allColorSets=True) or [])
    orig_dc_after = cmds.getAttr(f"{sphere}.displayColors")
    check(orig_sets_after == orig_sets_before, "原物体 color set 列表未被改动")
    check(orig_dc_after == orig_dc_before, "原物体 displayColors 状态未被改动")
    cmds.delete(dup)

    print("\n[7] 坐标约定切换 + 方向指示器投影(无头,不建 modelPanel)")
    from fbx_inspector.core.coord_convention import (
        CONVENTIONS,
        to_maya_matrix44,
        view_rotation_from_matrix,
    )
    from fbx_inspector.ui.axis_indicator import project_axes

    # 复现 IsolatedMeshView 的完整层级:dup → content → group,并把 group 平移到远处隐藏。
    OFFSET = 100000.0
    gdup = cmds.duplicate(sphere, name="__smoke_gdup__", returnRootsOnly=True)[0]
    content = cmds.group(gdup, name="__smoke_content__", world=True)
    ggroup = cmds.group(content, name="__smoke_ggroup__", world=True)
    cmds.setAttr(f"{ggroup}.translateX", OFFSET)

    # 切到 UE:content 上矩阵,验证 bbox 的 Y/Z 范围互换
    bb_maya = cmds.exactWorldBoundingBox(gdup)
    y_span_maya = bb_maya[4] - bb_maya[1]
    z_span_maya = bb_maya[5] - bb_maya[2]

    # 逐顶点世界坐标:切换前记一个非原点顶点,验证净变换正是 UE 的 (x,z,y)。
    # ggroup 的 X 偏移对切换前后相同(且只作用于 X),做差即抵消,故 Y/Z 直接可比。
    p_before = cmds.xform(f"{gdup}.vtx[5]", query=True, worldSpace=True, translation=True)

    faces_before = cmds.polyEvaluate(gdup, face=True)
    cmds.xform(content, matrix=to_maya_matrix44(CONVENTIONS["ue"].matrix), objectSpace=True)
    # UE 自己**不翻绕序**(靠左手系 front=CW 渲正面);副本在 Maya 右手视口,故镜像时反转一次
    # 法线补偿背面朝外。此举的**视觉**效果只能 GUI 手测(见本节末手测清单),这里仅确认拓扑不变。
    if CONVENTIONS["ue"].is_mirror:
        cmds.polyNormal(gdup, normalMode=0, userNormalMode=0, ch=False)
    faces_after = cmds.polyEvaluate(gdup, face=True)

    p_after = cmds.xform(f"{gdup}.vtx[5]", query=True, worldSpace=True, translation=True)
    check(
        abs(p_after[0] - p_before[0]) < 1e-3      # X 不变
        and abs(p_after[1] - p_before[2]) < 1e-3  # UE_Y = Maya_Z
        and abs(p_after[2] - p_before[1]) < 1e-3,  # UE_Z = Maya_Y
        "逐顶点世界坐标按 UE 净变换 (x,z,y) 互换: "
        f"{[round(v, 3) for v in p_before]} → {[round(v, 3) for v in p_after]}",
    )

    bb_ue = cmds.exactWorldBoundingBox(gdup)
    y_span_ue = bb_ue[4] - bb_ue[1]
    z_span_ue = bb_ue[5] - bb_ue[2]
    check(
        abs(y_span_ue - z_span_maya) < 1e-3 and abs(z_span_ue - y_span_maya) < 1e-3,
        "切到 UE 后副本 bbox 的 Y/Z 范围互换(Z-up 生效,与 UE 净变换一致)",
    )
    check(faces_after == faces_before, "坐标变换 + 法线反转不改拓扑(面数不变)")

    # 原物体完全不受这一节影响
    check(
        set(cmds.polyColorSet(sphere, query=True, allColorSets=True) or [])
        == orig_sets_before,
        "坐标节:原物体 color set 仍未被改动",
    )
    cmds.delete(ggroup)

    # 方向指示器投影:用真实相机的世界矩阵(不需要 modelPanel)驱动纯投影逻辑。
    cam = cmds.camera(name="__smoke_cam__")[0]
    cmds.setAttr(f"{cam}.rotate", -27.938, 45.0, 0.0)  # 与隔离视口相机同朝向
    m16 = cmds.xform(cam, query=True, worldSpace=True, matrix=True)
    vr = view_rotation_from_matrix(m16)
    axes = project_axes(vr, CONVENTIONS["ue"])
    norms = [(a.dx * a.dx + a.dy * a.dy + a.depth * a.depth) ** 0.5 for a in axes]
    check(
        len(axes) == 3 and all(abs(n - 1.0) < 1e-3 for n in norms),
        f"指示器投影出 3 根单位长度轴(实测模长 {[round(n, 3) for n in norms]})",
    )
    labels = {a.label.split(" ")[0] for a in axes}
    check(labels == {"X", "Y", "Z"}, f"三轴标签为 X/Y/Z(实测 {labels})")
    cmds.delete(cam)

    # —— GUI 手测清单(无头测不到"渲染像素",只能进 Maya GUI 肉眼核对)——
    # 无头可验证的部分:位置净变换 = UE 的 (x,z,y) 数值、拓扑不变、gizmo 投影出三根轴。
    # 关于"模型立起来":Maya 视口固定 Y-up,把 Z-up 的 UE 坐标塞进来显示,水平面会呈竖直——
    # 这是**预期现象、不是 bug**(本工具以数值正确为先,不追求副本姿态与 UE 视口逐帧一致)。
    print(
        "\n[7-GUI] 需在 Maya GUI 手测(open_inspector → 切 UE):\n"
        "  - 副本坐标值已转为 Z-up(与 UE 一致);因视口 Y-up,水平面会显示为‘立起来’,属预期;\n"
        "  - 不出现 inside-out / 黑面(polyNormal 补偿到位);\n"
        "  - 右上角 gizmo 显示 Z 朝上(蓝),随 tumble 转动;\n"
        "  - 切回 Maya 约定后模型/gizmo 复原,面数不变。"
    )

    print("\n[报告样例]\n" + report.to_text())

    print("\n" + ("=== 全部通过 ===" if not failures else f"=== {len(failures)} 项失败 ==="))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
