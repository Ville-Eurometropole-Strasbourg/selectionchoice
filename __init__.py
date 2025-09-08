import contextlib
import os

from qgis.core import (
    QgsCoordinateTransform,
    QgsFeatureRequest,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)
from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu
from qgis.utils import iface


class LayerChoiceSelectTool(QgsMapTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.selected_layer = None
        self.click_event = None
        self.click_point = None

    def canvasPressEvent(self, event):
        self.click_event = event
        self.click_point = self.toMapCoordinates(event.pos())
        self.show_layer_choice_menu(event)

    def transform_point_to_layer_crs(self, point, target_layer):
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        layer_crs = target_layer.crs()
        if canvas_crs != layer_crs:
            transform = QgsCoordinateTransform(
                canvas_crs, layer_crs, QgsProject.instance()
            )
            try:
                transformed_point = transform.transform(point)
                return transformed_point
            except Exception as e:
                iface.messageBar().pushMessage(
                    "Layer Choice Select",
                    f"Error transforming coordinates: {str(e)}",
                    level=2,
                    duration=5,
                )
                return point
        return point

    def create_selection_geometry(self, center_point, layer):
        transformed_point = self.transform_point_to_layer_crs(center_point, layer)
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        layer_crs = layer.crs()
        buffer_size = self.canvas.mapUnitsPerPixel() * 5
        if canvas_crs != layer_crs:
            canvas_point = center_point
            test_point = QgsPointXY(canvas_point.x() + buffer_size, canvas_point.y())
            transform = QgsCoordinateTransform(
                canvas_crs, layer_crs, QgsProject.instance()
            )
            try:
                transformed_center = transform.transform(canvas_point)
                transformed_test = transform.transform(test_point)
                buffer_size = transformed_center.distance(transformed_test)
            except Exception:
                pass
        point_geom = QgsGeometry.fromPointXY(transformed_point)
        buffer_geom = point_geom.buffer(buffer_size, 8)
        return buffer_geom

    def show_layer_choice_menu(self, event):
        vector_layers_with_features = []
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer):
                layer_tree = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
                if layer_tree and layer_tree.isVisible():
                    selection_geom = self.create_selection_geometry(
                                        self.click_point, layer
                                     )
                    request = QgsFeatureRequest().setFilterRect(
                                selection_geom.boundingBox()
                              )
                    matched_display_values = []
                    display_field = layer.displayField()
                    for feature in layer.getFeatures(request):
                        if feature.geometry().intersects(selection_geom):
                            if display_field in feature.fields().names():
                                attr_val = feature[display_field]
                            else:
                                attr_val = feature.id()
                            matched_display_values.append(str(attr_val))
                    if matched_display_values:
                        vector_layers_with_features.append(
                            (layer, matched_display_values)
                        )
        if not vector_layers_with_features:
            return
        menu = QMenu()
        menu.setTitle("Choose Layer")
        for layer, display_values in vector_layers_with_features:
            preview = ", ".join(display_values[:5])
            if len(display_values) > 5:
                preview += ", …"
            action_text = f"{layer.name()} ({preview})"
            action = menu.addAction(action_text)
            action.setData(layer)
            action.triggered.connect(
                lambda checked=False, layer=layer: self.layer_chosen(layer)
            )
        global_pos = self.canvas.mapToGlobal(event.pos())
        menu.exec_(global_pos)

    def layer_chosen(self, layer):
        self.selected_layer = layer
        selection_geom = self.create_selection_geometry(self.click_point, layer)
        self.select_features_with_geometry(selection_geom, self.click_event)
        self.reset_tool()

    def select_features_with_geometry(self, selection_geom, event):
        if not isinstance(self.selected_layer, QgsVectorLayer):
            return
        request = QgsFeatureRequest().setFilterRect(selection_geom.boundingBox())
        selected_features = []
        for feature in self.selected_layer.getFeatures(request):
            if feature.geometry().intersects(selection_geom):
                selected_features.append(feature)
        feature_ids = [f.id() for f in selected_features]
        modifiers = event.modifiers()
        if feature_ids:
            existing_ids = self.selected_layer.selectedFeatureIds()
            if modifiers & Qt.ControlModifier:
                new_selection = set(existing_ids)
                for fid in feature_ids:
                    if fid in new_selection:
                        new_selection.remove(fid)
                    else:
                        new_selection.add(fid)
                self.selected_layer.selectByIds(list(new_selection))
            elif modifiers & Qt.ShiftModifier:
                new_selection = set(existing_ids) - set(feature_ids)
                self.selected_layer.selectByIds(list(new_selection))
            else:
                self.selected_layer.selectByIds(feature_ids)
        else:
            if not (modifiers & (Qt.ControlModifier | Qt.ShiftModifier)):
                self.selected_layer.removeSelection()


    def reset_tool(self):
        self.selected_layer = None
        self.click_event = None
        self.click_point = None

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CrossCursor)

    def deactivate(self):
        self.reset_tool()
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
        icon_path = (
            os.path.join(self.plugin_dir, "icon.svg")
            if os.path.exists(os.path.join(self.plugin_dir, "icon.svg"))
            else None
        )
        self.tool_action = self.add_action(
            icon_path,
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
        if self.select_tool:
            if self.iface.mapCanvas().mapTool() == self.select_tool:
                self.iface.mapCanvas().unsetMapTool(self.select_tool)
                self.tool_action.setChecked(False)
            else:
                self.iface.mapCanvas().setMapTool(self.select_tool)

    def map_tool_changed(self, tool):
        if self.tool_action:
            self.tool_action.setChecked(tool == self.select_tool)


def classFactory(iface):
    return LayerChoiceSelectPlugin(iface)
