"""Plugin entry point: the Plugins-toolbar/menu UI and its wiring to
:class:`ScaleLockController`, which implements the actual locking
behaviour.

This module intentionally contains no scale math and no signal
interception logic of its own -- see ``scale_lock_controller.py`` and
``scale_utils.py`` for that.
"""

import os

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QAction, QIcon

from qgis.core import Qgis

from .scale_lock_controller import LockState, ScaleLockController

PLUGIN_NAME = "Zoom to Predefined Scales"
_PLUGIN_DIR = os.path.dirname(__file__)


class ZoomToPredefinedScalePlugin:
    """QGIS plugin object created by ``classFactory()``."""

    def __init__(self, iface):
        self.iface = iface
        self._action = None
        self._settings_action = None
        self._icon_locked = None
        self._icon_unlocked = None
        self._controller = None

    # ------------------------------------------------------- QGIS hooks

    def initGui(self) -> None:
        self._icon_unlocked = QIcon(os.path.join(_PLUGIN_DIR, "icon_unlocked.png"))
        self._icon_locked = QIcon(os.path.join(_PLUGIN_DIR, "icon.png"))

        action = QAction(self._icon_unlocked, PLUGIN_NAME, self.iface.mainWindow())
        action.setObjectName("zoomToPredefinedScaleAction")
        action.setCheckable(True)
        action.setToolTip(self.tr("Lock map canvas to project predefined scales"))
        action.setStatusTip(action.toolTip())
        action.triggered.connect(self._on_action_triggered)
        self._action = action

        self.iface.addToolBarIcon(action)
        self.iface.addPluginToMenu(f"&{PLUGIN_NAME}", action)

        # A second action under the same menu name makes QGIS group both
        # under a "Zoom to Predefined Scales" submenu automatically: Plugins
        # -> Zoom to Predefined Scales -> Settings...
        settings_action = QAction(self.tr("Settings..."), self.iface.mainWindow())
        settings_action.setObjectName("zoomToPredefinedScaleSettingsAction")
        settings_action.triggered.connect(self._open_settings)
        self._settings_action = settings_action
        self.iface.addPluginToMenu(f"&{PLUGIN_NAME}", settings_action)

        self._controller = ScaleLockController(self.iface)
        self._controller.stateChanged.connect(self._on_state_changed)
        # Reflect whatever state the controller already resolved (a project
        # may already be open, with or without usable predefined scales)
        # before the UI had a chance to listen for stateChanged.
        self._on_state_changed(self._controller.state)

    def unload(self) -> None:
        if self._controller is not None:
            self._controller.teardown()
            try:
                self._controller.stateChanged.disconnect(self._on_state_changed)
            except (TypeError, RuntimeError):
                pass
            self._controller = None

        if self._action is not None:
            self.iface.removePluginMenu(f"&{PLUGIN_NAME}", self._action)
            self.iface.removeToolBarIcon(self._action)
            self._action.deleteLater()
            self._action = None

        if self._settings_action is not None:
            self.iface.removePluginMenu(f"&{PLUGIN_NAME}", self._settings_action)
            self._settings_action.deleteLater()
            self._settings_action = None

        self._icon_locked = None
        self._icon_unlocked = None

    def tr(self, message: str) -> str:
        return QCoreApplication.translate("ZoomToPredefinedScale", message)

    # -------------------------------------------------------- UI slots

    def _open_settings(self) -> None:
        from .settings_dialog import SettingsDialog

        SettingsDialog(self.iface.mainWindow()).exec()

    def _on_action_triggered(self, checked: bool) -> None:
        controller = self._controller
        action = self._action
        if controller is None or action is None:
            return

        if checked and not controller.has_usable_scales():
            # Veto: revert the button and explain why via the message bar
            # instead of popping an intrusive dialog.
            action.blockSignals(True)
            action.setChecked(False)
            action.blockSignals(False)
            self._warn_no_scales()
            return

        controller.set_locked(checked)

    def _on_state_changed(self, state: str) -> None:
        action = self._action
        if action is None:
            return

        action.blockSignals(True)
        try:
            if state == LockState.LOCKED:
                action.setChecked(True)
                action.setEnabled(True)
                action.setIcon(self._icon_locked)
                action.setToolTip(self.tr("Unlock map canvas from predefined scales"))
            elif state == LockState.UNLOCKED:
                action.setChecked(False)
                action.setEnabled(True)
                action.setIcon(self._icon_unlocked)
                action.setToolTip(self.tr("Lock map canvas to project predefined scales"))
            else:  # LockState.UNAVAILABLE
                action.setChecked(False)
                action.setEnabled(True)  # stays clickable so the user gets the warning
                action.setIcon(self._icon_unlocked)
                action.setToolTip(
                    self.tr(
                        "No usable predefined scales in this project\n"
                        "(Project → Properties → View Settings → "
                        "Project predefined scales)"
                    )
                )
        finally:
            action.blockSignals(False)
        action.setStatusTip(action.toolTip())

    def _warn_no_scales(self) -> None:
        bar = self.iface.messageBar()
        if bar is None:
            return
        bar.pushMessage(
            PLUGIN_NAME,
            self.tr(
                "This project has no usable predefined scales. Enable "
                "“Project predefined scales” and add at least one "
                "scale in Project → Properties … → View "
                "Settings."
            ),
            level=Qgis.MessageLevel.Warning,
            duration=6,
        )
