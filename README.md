# Layer Choice Select Plugin for QGIS

**Layer Choice Select** is a QGIS plugin that enhances the feature selection process by allowing users to **choose which visible vector layer** to select features from when clicking on the map canvas. This is particularly useful when multiple layers overlap spatially, and you want precise control over which layer's features get selected.

---

## 🔍 Features

- Click on the map to trigger a **popup menu** showing all visible vector layers that have features under the clicked point.
- View a **preview of matching features** (by display field or feature ID) for each layer.
- Easily select features from the chosen layer using a **buffered selection** around the click point.
- Supports modifier keys:
  - **Ctrl**: Add/remove from current selection.
  - **Shift**: Deselect from current selection.
  - No modifier: Replace selection.

---

## 🚀 How It Works

1. Click on the map canvas.
2. The plugin checks all **visible vector layers** for features that intersect a small buffer around the clicked point.
3. A **context menu** appears with a list of matching layers and their nearby feature values.
4. Choose a layer from the menu.
5. The plugin selects intersecting features in the selected layer.

---

## 📦 Installation

1. Install the .zip package found in the releases using the Qgis extension tool.
2. You will see a new toolbar button labeled **"Selection with layer choice"**.

---

## 🖱️ Usage

1. Activate the plugin via the toolbar or plugin menu.
2. Click anywhere on the map.
3. A popup will show available layers with intersecting features.
4. Select the desired layer to perform the feature selection.

---

## 🧪 Tested With

- QGIS 3.44

---

## 📝 License

This plugin is provided as-is under the **AGPLv3 License**. See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Pull requests and issues are welcome! Please ensure compatibility with the QGIS plugin system and follow Pythonic code style.

---

## 💡 Tip

If your layers do not show in the selection menu:
- Ensure they are **visible** in the layer panel.
- Ensure they are **vector layers** with spatial features.
