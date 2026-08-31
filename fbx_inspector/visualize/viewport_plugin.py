"""Maya Viewport 2.0 绘制插件：在三维点旁显示数字标签。"""

from __future__ import annotations

import json

import maya.api.OpenMaya as om  # type: ignore[import-not-found]
import maya.api.OpenMayaRender as omr  # type: ignore[import-not-found]
import maya.api.OpenMayaUI as omui  # type: ignore[import-not-found]

NODE_TYPE = "fbxInspectorValueLabels"
NODE_ID = om.MTypeId(0x0013B2A1)
DRAW_CLASSIFICATION = "drawdb/geometry/fbxInspectorValueLabels"
DRAW_REGISTRANT = "FbxInspectorValueLabelsRegistrant"
DEFAULT_LABEL_COLOR = (230 / 255, 81 / 255, 0.0, 1.0)


def maya_useNewAPI():
    """通知 Maya 以 Python API 2.0 对象调用插件入口。"""


class ValueLabelNode(omui.MPxLocatorNode):
    labels_json = om.MObject()
    font_size = om.MObject()

    @staticmethod
    def creator():
        return ValueLabelNode()

    def isBounded(self):  # noqa: N802
        """标签散布在整个网格上，不能按 locator 原点的小包围盒裁剪。"""
        return False

    @staticmethod
    def initialize():
        typed = om.MFnTypedAttribute()
        ValueLabelNode.labels_json = typed.create("labelsJson", "lj", om.MFnData.kString)
        typed.writable = True
        typed.storable = True
        ValueLabelNode.addAttribute(ValueLabelNode.labels_json)
        numeric = om.MFnNumericAttribute()
        ValueLabelNode.font_size = numeric.create("fontSize", "fs", om.MFnNumericData.kInt, 12)
        numeric.setMin(1)
        numeric.setMax(96)
        numeric.writable = True
        numeric.storable = True
        ValueLabelNode.addAttribute(ValueLabelNode.font_size)


class LabelDrawData(om.MUserData):
    def __init__(self):
        super().__init__(False)
        self.labels = []
        self.font_size = 12
        self.color = DEFAULT_LABEL_COLOR


class ValueLabelDrawOverride(omr.MPxDrawOverride):
    def __init__(self, obj):
        super().__init__(obj, None, False)

    @staticmethod
    def creator(obj):
        return ValueLabelDrawOverride(obj)

    def supportedDrawAPIs(self):  # noqa: N802
        return omr.MRenderer.kAllDevices

    def hasUIDrawables(self):  # noqa: N802
        return True

    def prepareForDraw(self, obj_path, camera_path, frame_context, old_data):  # noqa: N802
        data = old_data if isinstance(old_data, LabelDrawData) else LabelDrawData()
        node = om.MFnDependencyNode(obj_path.node())
        raw = node.findPlug("labelsJson", False).asString()
        try:
            payload = json.loads(raw) if raw else []
            if isinstance(payload, dict):
                data.labels = payload.get("labels", [])
                color = payload.get("color", DEFAULT_LABEL_COLOR)
                data.color = tuple(float(c) for c in color[:4])
            else:
                data.labels = payload
                data.color = DEFAULT_LABEL_COLOR
        except (TypeError, ValueError):
            data.labels = []
            data.color = DEFAULT_LABEL_COLOR
        data.font_size = node.findPlug("fontSize", False).asInt()
        return data

    def addUIDrawables(self, obj_path, draw_manager, frame_context, data):  # noqa: N802
        if not isinstance(data, LabelDrawData):
            return
        draw_manager.beginDrawable()
        draw_manager.setColor(om.MColor(data.color))
        draw_manager.setFontSize(data.font_size)
        for item in data.labels:
            point = item.get("p", (0.0, 0.0, 0.0))
            position = om.MPoint(float(point[0]), float(point[1]) + 0.001, float(point[2]))
            draw_manager.text(position, str(item.get("text", "")), omr.MUIDrawManager.kLeft)
        draw_manager.endDrawable()


def initializePlugin(obj):  # noqa: N802
    plugin = om.MFnPlugin(obj, "maya-fbx-asset-inspector", "2.0", "Any")
    plugin.registerNode(
        NODE_TYPE, NODE_ID, ValueLabelNode.creator, ValueLabelNode.initialize,
        om.MPxNode.kLocatorNode, DRAW_CLASSIFICATION,
    )
    omr.MDrawRegistry.registerDrawOverrideCreator(
        DRAW_CLASSIFICATION, DRAW_REGISTRANT, ValueLabelDrawOverride.creator
    )


def uninitializePlugin(obj):  # noqa: N802
    omr.MDrawRegistry.deregisterDrawOverrideCreator(DRAW_CLASSIFICATION, DRAW_REGISTRANT)
    om.MFnPlugin(obj).deregisterNode(NODE_ID)
