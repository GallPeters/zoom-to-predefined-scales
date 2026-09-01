"""Owns the lock on/off state and the signal wiring that enforces it.

Design summary (see README.md for the full rationale):

    * We never poll and never install an event filter on the canvas. We let
      QGIS handle every zoom interaction (wheel, zoom in/out tool, rubber
      band zoom, keyboard shortcuts, ...) exactly as it always does, and we
      react to :pyattr:`QgsMapCanvas.scaleChanged`, the native signal QGIS
      already emits whenever the canvas scale settles on a new value.
    * When locked, each ``scaleChanged`` tells us QGIS just landed on some
      arbitrary scale as a result of *some* zoom action. We compare that
      scale to the last predefined scale we were sitting on to infer the
      zoom direction, compute the correct predefined scale with
      :mod:`scale_utils`, and immediately re-zoom to it with
      ``QgsMapCanvas.zoomScale()`` -- the same call QGIS's own scale box
      uses, which re-centres on the canvas' *current* centre. Because the
      native zoom already re-centred the view on the cursor (for wheel
      zoom) or on the drawn rectangle (for rubber-band zoom), pivoting the
      correction around that already-adjusted centre preserves the user's
      focal point.
    * A single re-entrancy guard (``_applying_correction``) makes sure the
      ``scaleChanged`` that our own correction emits is ignored instead of
      triggering another correction.
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from qgis.core import Qgis, QgsMessageLog, QgsProject

from .project_scales import ScaleAvailability, get_project_predefined_scales
from .scale_utils import is_close, nearest_scale, next_scale

_LOG_TAG = "Zoom to Predefined Scales"


class LockState:
    """Public states the controller (and therefore the UI) can be in."""

    UNLOCKED = "unlocked"
    LOCKED = "locked"
    #: Locking was requested/possible in principle, but the current project
    #: has no usable predefined scales to lock to.
    UNAVAILABLE = "unavailable"


class ScaleLockController(QObject):
    """Watches the active project for predefined map scales and, while
    locked, keeps every canvas zoom operation snapped to that scale list.
    """

    #: Emitted whenever the effective UI state changes (one of LockState.*).
    stateChanged = pyqtSignal(str)

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self._iface = iface
        self._canvas = iface.mapCanvas()

        self._locked = False
        self._applying_correction = False  # re-entrancy guard
        self._locked_scale = None          # last predefined scale we settled on
        self._availability = ScaleAvailability.NO_PROJECT
        self._scales = ()

        self._project = None
        self._view_settings = None

        self._connect_project(QgsProject.instance())

    # ---------------------------------------------------------------- API

    @property
    def locked(self) -> bool:
        return self._locked

    @property
    def availability(self) -> str:
        return self._availability

    @property
    def scales(self) -> tuple:
        return self._scales

    @property
    def state(self) -> str:
        return self._current_state()

    def has_usable_scales(self) -> bool:
        return self._availability == ScaleAvailability.ENABLED_WITH_SCALES

    def set_locked(self, locked: bool) -> None:
        """Engage or release the lock. Refuses to engage when there are no
        usable predefined scales (callers should check
        :meth:`has_usable_scales` first to decide whether to warn the
        user)."""
        locked = bool(locked)
        if locked == self._locked:
            return

        if locked and not self.has_usable_scales():
            self.stateChanged.emit(self._current_state())
            return

        self._locked = locked
        if locked:
            self._canvas.scaleChanged.connect(self._on_canvas_scale_changed)
            self._snap_to_nearest_scale()
        else:
            self._safe_disconnect(self._canvas.scaleChanged, self._on_canvas_scale_changed)
            self._locked_scale = None

        self.stateChanged.emit(self._current_state())

    def teardown(self) -> None:
        """Disconnect every signal this controller ever connected. Safe to
        call multiple times and at any point in the plugin lifecycle."""
        if self._locked:
            self._safe_disconnect(self._canvas.scaleChanged, self._on_canvas_scale_changed)
        self._locked = False
        self._locked_scale = None
        self._disconnect_project()

    # ---------------------------------------------------------- internals

    @staticmethod
    def _safe_disconnect(signal, slot) -> None:
        try:
            signal.disconnect(slot)
        except (TypeError, RuntimeError):
            # Already disconnected, or the underlying Qt object is gone.
            pass

    def _log_error(self, context: str, exc: Exception) -> None:
        QgsMessageLog.logMessage(f"{context}: {exc}", _LOG_TAG, Qgis.MessageLevel.Critical)

    # -- project / view-settings wiring ----------------------------------

    def _connect_project(self, project) -> None:
        if project is None:
            return
        project.readProject.connect(self._on_project_changed)
        project.cleared.connect(self._on_project_changed)
        self._project = project
        self._refresh_from_project(project)

    def _disconnect_project(self) -> None:
        if self._project is not None:
            self._safe_disconnect(self._project.readProject, self._on_project_changed)
            self._safe_disconnect(self._project.cleared, self._on_project_changed)
        self._project = None
        self._disconnect_view_settings()

    def _disconnect_view_settings(self) -> None:
        if self._view_settings is not None:
            self._safe_disconnect(self._view_settings.mapScalesChanged, self._on_scales_changed)
        self._view_settings = None

    def _on_project_changed(self, *_args) -> None:
        try:
            self._refresh_from_project(QgsProject.instance())
        except Exception as exc:  # noqa: BLE001 - must never break QGIS
            self._log_error("Error handling project change", exc)

    def _refresh_from_project(self, project) -> None:
        self._disconnect_view_settings()

        view_settings = project.viewSettings() if project is not None else None
        if view_settings is not None:
            view_settings.mapScalesChanged.connect(self._on_scales_changed)
            self._view_settings = view_settings

        self._on_scales_changed()

    def _on_scales_changed(self, *_args) -> None:
        try:
            availability, scales = get_project_predefined_scales(
                self._project if self._project is not None else QgsProject.instance()
            )
        except Exception as exc:  # noqa: BLE001
            self._log_error("Error reading project predefined scales", exc)
            availability, scales = ScaleAvailability.NO_PROJECT, ()

        self._availability = availability
        self._scales = scales

        if self._locked and availability != ScaleAvailability.ENABLED_WITH_SCALES:
            # Scales disappeared/got disabled out from under an active
            # lock: fall back to unlocked rather than enforcing a stale or
            # empty list.
            self.set_locked(False)
            return

        if self._locked:
            # Re-anchor to the (possibly changed) scale list, but only move
            # the canvas if the scale we were locked to is no longer valid.
            self._snap_to_nearest_scale(only_if_invalid=True)

        self.stateChanged.emit(self._current_state())

    # -- zoom interception ------------------------------------------------

    def _on_canvas_scale_changed(self, new_scale: float) -> None:
        if self._applying_correction:
            return
        if not self._locked or not self._scales:
            return

        try:
            reference = self._locked_scale if self._locked_scale is not None else new_scale
            if is_close(new_scale, reference):
                return
            zoom_in = new_scale < reference

            target = next_scale(self._scales, reference, zoom_in)
            if target is None:
                return

            self._apply_scale(target)
        except Exception as exc:  # noqa: BLE001 - never break canvas navigation
            self._log_error("Error correcting zoom to a predefined scale", exc)
            self._applying_correction = False

    def _snap_to_nearest_scale(self, only_if_invalid: bool = False) -> None:
        if not self._scales:
            return

        if only_if_invalid and self._locked_scale is not None:
            if any(is_close(self._locked_scale, s) for s in self._scales):
                return

        reference = self._locked_scale if self._locked_scale is not None else self._canvas.scale()
        target = nearest_scale(self._scales, reference)
        if target is not None:
            self._apply_scale(target)

    def _apply_scale(self, target_scale: float) -> None:
        self._applying_correction = True
        try:
            # ignoreScaleLock=True: QGIS has its own, unrelated "lock scale"
            # toggle (QgsMapCanvas.setScaleLocked(), the padlock next to the
            # status bar scale box) that freezes the scale and turns further
            # zooming into magnification instead. That feature must not be
            # able to silently swallow our predefined-scale correction.
            self._canvas.zoomScale(target_scale, True)
        finally:
            self._applying_correction = False
        self._locked_scale = target_scale

    def _current_state(self) -> str:
        if self._locked:
            return LockState.LOCKED
        if self._availability == ScaleAvailability.ENABLED_WITH_SCALES:
            return LockState.UNLOCKED
        return LockState.UNAVAILABLE
