# -*- coding: utf-8 -*-
"""Tests for ScaleLockController: lock/unlock transitions, zoom-direction
correction, the recursion guard, and reacting to project/scale changes.

Uses FakeIface/FakeCanvas (fakes.py) as a stand-in for the real QGIS
canvas/interface objects (so no real map render pipeline is needed), and the
real ``qgis.core.QgsProject`` singleton (bootstrapped via ``qgis.testing`` in
tests/__init__.py) for everything project-related.
"""

import unittest

from qgis.core import QgsProject

from _ztps_plugin.scale_lock_controller import LockState, ScaleLockController

from .fakes import FakeCanvas, FakeIface


def _configure_scales(scales, enabled=True):
    view_settings = QgsProject.instance().viewSettings()
    view_settings.setMapScales(scales)
    view_settings.setUseProjectScales(enabled)


class ScaleLockControllerTests(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()

    def test_starts_unavailable_when_project_has_no_predefined_scales(self):
        controller = ScaleLockController(FakeIface())
        self.assertEqual(controller.state, LockState.UNAVAILABLE)
        self.assertFalse(controller.has_usable_scales())

    def test_starts_unlocked_when_project_already_has_usable_scales(self):
        _configure_scales([100000, 50000, 25000, 10000])
        controller = ScaleLockController(FakeIface())
        self.assertEqual(controller.state, LockState.UNLOCKED)
        self.assertTrue(controller.has_usable_scales())

    def test_set_locked_refused_without_usable_scales(self):
        controller = ScaleLockController(FakeIface())
        controller.set_locked(True)
        self.assertFalse(controller.locked)
        self.assertEqual(controller.state, LockState.UNAVAILABLE)

    def test_engaging_lock_snaps_current_scale_to_nearest_predefined_scale(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=48000.0)
        controller = ScaleLockController(FakeIface(canvas))

        controller.set_locked(True)

        self.assertTrue(controller.locked)
        self.assertEqual(controller.state, LockState.LOCKED)
        self.assertEqual(canvas.scale(), 50000.0)

    def test_zoom_in_native_event_corrects_to_next_smaller_predefined_scale(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=50000.0)
        controller = ScaleLockController(FakeIface(canvas))
        controller.set_locked(True)
        self.assertEqual(canvas.scale(), 50000.0)

        # Simulate QGIS's own zoom (e.g. one wheel notch) landing on some
        # arbitrary smaller (zoomed-in) scale.
        canvas.simulate_native_zoom(38000.0)

        self.assertEqual(canvas.scale(), 25000.0)

    def test_zoom_out_native_event_corrects_to_next_larger_predefined_scale(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=50000.0)
        controller = ScaleLockController(FakeIface(canvas))
        controller.set_locked(True)

        canvas.simulate_native_zoom(63000.0)

        self.assertEqual(canvas.scale(), 100000.0)

    def test_unlocked_state_leaves_native_zoom_untouched(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=50000.0)
        controller = ScaleLockController(FakeIface(canvas))
        self.assertFalse(controller.locked)

        canvas.simulate_native_zoom(37123.456)

        # No correction applied: the controller isn't even listening yet.
        self.assertEqual(canvas.scale(), 37123.456)
        self.assertEqual(canvas.zoom_calls, [])

    def test_recursion_guard_prevents_reacting_to_its_own_correction(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=50000.0)
        controller = ScaleLockController(FakeIface(canvas))
        # 1 zoomScale call: the snap onto 50000 (a no-op value, still applied).
        controller.set_locked(True)

        # Triggers exactly 1 corrective zoomScale call.
        canvas.simulate_native_zoom(38000.0)

        # Exactly two zoomScale calls total ever happened: the initial snap
        # and the single correction. If the recursion guard failed, the
        # corrective zoomScale(25000) call's own scaleChanged(25000) would
        # re-trigger the handler and this would grow without bound.
        self.assertEqual(canvas.zoom_calls, [50000.0, 25000.0])

    def test_unlocking_stops_reacting_to_further_zoom_events(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=50000.0)
        controller = ScaleLockController(FakeIface(canvas))
        controller.set_locked(True)
        controller.set_locked(False)

        canvas.simulate_native_zoom(38000.0)

        # Left untouched: normal QGIS behaviour restored.
        self.assertEqual(canvas.scale(), 38000.0)

    def test_project_scales_removed_while_locked_falls_back_to_unavailable(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=50000.0)
        controller = ScaleLockController(FakeIface(canvas))
        controller.set_locked(True)

        QgsProject.instance().viewSettings().setUseProjectScales(False)

        self.assertFalse(controller.locked)
        self.assertEqual(controller.state, LockState.UNAVAILABLE)

        # And zoom operations are no longer intercepted.
        canvas.simulate_native_zoom(12345.0)
        self.assertEqual(canvas.scale(), 12345.0)

    def test_scale_list_change_while_locked_resnaps_if_current_scale_dropped(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=50000.0)
        controller = ScaleLockController(FakeIface(canvas))
        controller.set_locked(True)
        self.assertEqual(canvas.scale(), 50000.0)

        # 50000 is removed from the list.
        _configure_scales([100000, 20000, 10000])

        self.assertTrue(controller.locked)
        # Re-snapped to the nearest remaining scale.
        self.assertIn(canvas.scale(), (100000.0, 20000.0))

    def test_scale_list_change_while_locked_keeps_scale_if_still_valid(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=50000.0)
        controller = ScaleLockController(FakeIface(canvas))
        controller.set_locked(True)
        calls_before = list(canvas.zoom_calls)

        # Unrelated edit that keeps 50000 in the list.
        _configure_scales([100000, 50000, 25000, 10000, 5000])

        self.assertTrue(controller.locked)
        self.assertEqual(canvas.zoom_calls, calls_before)  # no unnecessary re-zoom

    def test_project_closed_resets_state(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=50000.0)
        controller = ScaleLockController(FakeIface(canvas))
        controller.set_locked(True)

        # QgsProject.clear() is what QGIS calls both when closing a project
        # and before loading a new one; it emits the real `cleared` signal.
        QgsProject.instance().clear()

        self.assertFalse(controller.locked)
        self.assertEqual(controller.state, LockState.UNAVAILABLE)

        # And a stale scale list must not still be enforced afterwards.
        canvas.simulate_native_zoom(12345.0)
        self.assertEqual(canvas.scale(), 12345.0)

    def test_teardown_disconnects_everything(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=50000.0)
        controller = ScaleLockController(FakeIface(canvas))
        controller.set_locked(True)

        controller.teardown()

        canvas.simulate_native_zoom(38000.0)
        self.assertEqual(canvas.scale(), 38000.0)  # untouched: no listeners left

        # Changing project scales afterwards must not raise or reconnect.
        _configure_scales([1000, 2000])

    def test_teardown_is_safe_to_call_twice(self):
        controller = ScaleLockController(FakeIface())
        controller.teardown()
        controller.teardown()  # must not raise


if __name__ == "__main__":
    unittest.main()
