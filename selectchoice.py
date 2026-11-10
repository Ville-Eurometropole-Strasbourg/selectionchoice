import contextlib
import os

from qgis.core import (
    QgsCoordinateTransform,
    QgsCsException,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeatureRequest,
    QgsProject,
    QgsRectangle,
    QgsRenderContext,
    QgsVectorLayer,
)
from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu
from qgis.utils import iface

TOLERANCE_PX = 5
PREVIEW_COUNT = 5

class LayerChoiceSelectTool(QgsMapTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.click_point = None
        self.modifiers = Qt.NoModifier
        self.matches = {}

    def canvasPressEvent(self, event):
        self.click_point = self.toMapCoordinates(event.pos())
        self.modifiers = event.modifiers()
        self.matches = {}
        self.canvas.setCursor(Qt.WaitCursor)
        try:
            self.show_layer_choice_menu(event)
        finally:
            self.canvas.setCursor(Qt.CrossCursor)

    def click_rect(self, layer):
        r = self.canvas.mapUnitsPerPixel() * TOLERANCE_PX
        p = self.click_point
        rect = QgsRectangle(p.x() - r, p.y() - r, p.x() + r, p.y() + r)
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        if canvas_crs != layer.crs():
            transform = QgsCoordinateTransform(
                canvas_crs, layer.crs(), QgsProject.instance()
            )
            try:
                return transform.transformBoundingBox(rect)
            except QgsCsException:
                return None
        return rect

    def find_matches(self, layer):
        rect = self.click_rect(layer)
        if rect is None:
            return None
        request = QgsFeatureRequest().setFilterRect(rect)
        request.setFlags(QgsFeatureRequest.ExactIntersect)
        idx = layer.fields().lookupField(layer.displayField())
        ids, preview = [], []

        def add(feature):
            ids.append(feature.id())
            if len(preview) < PREVIEW_COUNT:
                preview.append(str(feature[idx]) if idx >= 0 else str(feature.id()))
        renderer = layer.renderer()
        if renderer is None or renderer.type() == "singleSymbol":
            for feature in layer.getFeatures(request):
                add(feature)
        else:
            renderer = renderer.clone()  # ne pas toucher au renderer actif
            context = QgsRenderContext.fromMapSettings(self.canvas.mapSettings())
            context.setRendererScale(self.canvas.scale())
            expression_context = QgsExpressionContext()
            expression_context.appendScopes(
                QgsExpressionContextUtils.globalProjectLayerScopes(layer)
            )
            context.setExpressionContext(expression_context)
            renderer.startRender(context, layer.fields())
            try:
                for feature in layer.getFeatures(request):
                    expression_context.setFeature(feature)
                    if renderer.symbolsForFeature(
                        feature, context
                    ) and renderer.willRenderFeature(feature, context):
                        add(feature)
            finally:
                renderer.stopRender(context)
        return (ids, preview, len(ids)) if ids else None

    def candidate_layers(self):
        scale = self.canvas.scale()
        return [
            layer
            for layer in self.canvas.layers()
            if isinstance(layer, QgsVectorLayer)
            and layer.isSpatial()
            and layer.isInScaleRange(scale)
        ]

    def show_layer_choice_menu(self, event):
        for layer in self.candidate_layers():
            result = self.find_matches(layer)
            if result:
                self.matches[layer] = result
        if not self.matches:
            return
        if len(self.matches) == 1:
            self.layer_chosen(next(iter(self.matches)))
            return
        menu = QMenu()
        menu.setTitle("Choose Layer")
        for layer, (_, preview, total) in self.matches.items():
            text = ", ".join(preview) + (", …" if total > len(preview) else "")
            action = menu.addAction(f"{layer.name()} ({text})")
            action.triggered.connect(lambda _, layer=layer: self.layer_chosen(layer))
        self.canvas.setCursor(Qt.CrossCursor)
        menu.exec_(self.canvas.mapToGlobal(event.pos()))

    def layer_chosen(self, layer):
        ids = set(self.matches[layer][0])
        current = set(layer.selectedFeatureIds())
        mods = self.modifiers
        if mods & Qt.ControlModifier:
            new = current ^ ids
        elif mods & Qt.ShiftModifier:
            new = current - ids
        else:
            new = ids
        layer.selectByIds(list(new))
        iface.setActiveLayer(layer)

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CrossCursor)

    def deactivate(self):
        self.matches = {}
        super().deactivate()


class LayerChoiceSelectPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.toolbar = self.iface.addToolBar("Selection with layer choice")
        self.toolbar.setObjectName("LayerChoiceSelect")
        self.actions = []
        self.select_tool = None
        self.tool_action = None

    def add_action(self, icon_path, text, callback, parent=None, status_tip=None):
        icon = QIcon(icon_path) if icon_path else QIcon()
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setCheckable(True)
        if status_tip:
            action.setStatusTip(status_tip)
        self.toolbar.addAction(action)
        self.iface.addPluginToMenu("&Layer Choice Select", action)
        self.actions.append(action)
        return action

    def initGui(self):
        icon_file = os.path.join(self.plugin_dir, "icon.svg")
        self.tool_action = self.add_action(
            icon_file if os.path.exists(icon_file) else None,
            text="Selection with layer choice",
            callback=self.activate_select_tool,
            parent=self.iface.mainWindow(),
        )
        self.select_tool = LayerChoiceSelectTool(self.iface.mapCanvas())
        self.iface.mapCanvas().mapToolSet.connect(self.map_tool_changed)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu("&Layer Choice Select", action)
            self.iface.removeToolBarIcon(action)
        if self.toolbar:
            del self.toolbar
        with contextlib.suppress(Exception):
            self.iface.mapCanvas().mapToolSet.disconnect(self.map_tool_changed)

    def activate_select_tool(self):
        canvas = self.iface.mapCanvas()
        if canvas.mapTool() == self.select_tool:
            canvas.unsetMapTool(self.select_tool)
            self.tool_action.setChecked(False)
        else:
            canvas.setMapTool(self.select_tool)

    def map_tool_changed(self, tool):
        if self.tool_action:
            self.tool_action.setChecked(tool == self.select_tool)