# -*- coding: utf-8 -*-
"""Fake ``iface`` / ``QgsMapCanvas`` test doubles.

These stand in for the real ``QgisInterface``/``QgsMapCanvas`` QGIS only
ever provides inside a running application, so the controller and UI
lifecycle can be exercised without needing a full map canvas render
pipeline (an extent, a CRS, visible layers, ...). ``FakeCanvas`` is a real
``QObject`` with a real ``pyqtSignal`` so it behaves exactly like the real
canvas from the controller's point of view: ``.connect()``/``.disconnect()``
/``.emit()`` all behave identically to the genuine
``QgsMapCanvas.scaleChanged``.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class FakeCanvas(QObject):
    """Stands in for QgsMapCanvas: only the scale-related surface the
    controller uses."""

    scaleChanged = pyqtSignal(float)

    def __init__(self, initial_scale: float = 50000.0, parent=None):
        super().__init__(parent)
        self._scale = float(initial_scale)
        self.zoom_calls: list[float] = []

    def scale(self) -> float:
        return self._scale

    def zoomScale(self, scale: float, ignore_scale_lock: bool = False) -> None:
        """Mirrors QgsMapCanvas.zoomScale(): sets the scale and emits
        scaleChanged, synchronously, exactly like the real canvas does."""
        self.zoom_calls.append(scale)
        self._scale = scale
        self.scaleChanged.emit(scale)

    def simulate_native_zoom(self, scale: float) -> None:
        """Simulate QGIS's own zoom handling (wheel/tool/keyboard) landing
        the canvas on some arbitrary new scale, *before* the plugin reacts
        to it."""
        self._scale = scale
        self.scaleChanged.emit(scale)


class FakeMessageBar:
    def __init__(self):
        self.messages: list = []

    def pushMessage(self, *args, **kwargs) -> None:
        self.messages.append((args, kwargs))


class FakeIface:
    """Stands in for QgisInterface: the toolbar/menu surface used by
    zoom_to_predefined_scale.py, plus mapCanvas()/messageBar()/mainWindow()
    used by ScaleLockController."""

    def __init__(self, canvas: "FakeCanvas | None" = None):
        self._canvas = canvas or FakeCanvas()
        self._message_bar = FakeMessageBar()
        self.toolbar_actions: list = []
        self.menu_actions: dict = {}

    def mapCanvas(self) -> FakeCanvas:
        return self._canvas

    def messageBar(self) -> FakeMessageBar:
        return self._message_bar

    def mainWindow(self):
        return None

    def addToolBarIcon(self, action) -> None:
        self.toolbar_actions.append(action)

    def removeToolBarIcon(self, action) -> None:
        if action in self.toolbar_actions:
            self.toolbar_actions.remove(action)

    def addPluginToMenu(self, name, action) -> None:
        self.menu_actions.setdefault(name, []).append(action)

    def removePluginMenu(self, name, action) -> None:
        actions = self.menu_actions.get(name)
        if actions and action in actions:
            actions.remove(action)
