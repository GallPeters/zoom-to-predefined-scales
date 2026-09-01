# -*- coding: utf-8 -*-
"""End-to-end tests for the toolbar/menu UI lifecycle
(ZoomToPredefinedScalePlugin.initGui/unload), using real QAction/QIcon
objects (via the QApplication qgis.testing.start_app() already created in
tests/__init__.py) so the actual Qt signal wiring is exercised, not just the
plain-Python controller logic.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import QgsProject  # noqa: E402

from _ztps_plugin.scale_lock_controller import LockState  # noqa: E402
from _ztps_plugin.zoom_to_predefined_scale import ZoomToPredefinedScalePlugin  # noqa: E402

from .fakes import FakeCanvas, FakeIface  # noqa: E402


def _configure_scales(scales, enabled=True):
    view_settings = QgsProject.instance().viewSettings()
    view_settings.setMapScales(scales)
    view_settings.setUseProjectScales(enabled)


class PluginLifecycleTests(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().clear()

    def test_init_gui_adds_a_single_toolbar_and_menu_action(self):
        iface = FakeIface()
        plugin = ZoomToPredefinedScalePlugin(iface)

        plugin.initGui()

        self.assertEqual(len(iface.toolbar_actions), 1)
        self.assertIs(iface.toolbar_actions[0], plugin._action)
        self.assertEqual(sum(len(a) for a in iface.menu_actions.values()), 2)  # toggle + Settings

        plugin.unload()

    def test_action_reflects_unavailable_state_when_no_scales_configured(self):
        iface = FakeIface()
        plugin = ZoomToPredefinedScalePlugin(iface)
        plugin.initGui()

        action = plugin._action
        self.assertFalse(action.isChecked())
        self.assertTrue(action.isEnabled())
        self.assertIn("No usable predefined scales", action.toolTip())

        plugin.unload()

    def test_clicking_action_locks_and_updates_tooltip_icon(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=50000.0)
        iface = FakeIface(canvas)
        plugin = ZoomToPredefinedScalePlugin(iface)
        plugin.initGui()

        action = plugin._action
        self.assertEqual(action.toolTip(), "Lock map canvas to project predefined scales")

        action.trigger()  # simulates the user clicking the toolbar button

        self.assertTrue(plugin._controller.locked)
        self.assertTrue(action.isChecked())
        self.assertEqual(action.toolTip(), "Unlock map canvas from predefined scales")
        self.assertEqual(action.icon().cacheKey(), plugin._icon_locked.cacheKey())

        action.trigger()  # click again to unlock

        self.assertFalse(plugin._controller.locked)
        self.assertFalse(action.isChecked())
        self.assertEqual(action.toolTip(), "Lock map canvas to project predefined scales")

        plugin.unload()

    def test_clicking_action_without_usable_scales_warns_and_stays_unchecked(self):
        iface = FakeIface()
        plugin = ZoomToPredefinedScalePlugin(iface)
        plugin.initGui()

        action = plugin._action
        action.trigger()

        self.assertFalse(plugin._controller.locked)
        self.assertFalse(action.isChecked())
        self.assertEqual(len(iface.messageBar().messages), 1)

        plugin.unload()

    def test_live_zoom_while_locked_is_corrected_through_the_real_action(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=50000.0)
        iface = FakeIface(canvas)
        plugin = ZoomToPredefinedScalePlugin(iface)
        plugin.initGui()
        plugin._action.trigger()  # lock

        canvas.simulate_native_zoom(38000.0)

        self.assertEqual(canvas.scale(), 25000.0)  # snapped to the next smaller predefined scale

        plugin.unload()

    def test_project_scales_becoming_available_after_init_gui_updates_button(self):
        iface = FakeIface()
        plugin = ZoomToPredefinedScalePlugin(iface)
        plugin.initGui()
        self.assertTrue(plugin._action.isEnabled())
        self.assertEqual(plugin._controller.state, LockState.UNAVAILABLE)

        _configure_scales([50000, 25000])  # project settings changed after the plugin loaded

        self.assertEqual(plugin._controller.state, LockState.UNLOCKED)
        self.assertEqual(plugin._action.toolTip(), "Lock map canvas to project predefined scales")

        plugin.unload()

    def test_unload_removes_toolbar_and_menu_actions_and_stops_reacting(self):
        _configure_scales([100000, 50000, 25000, 10000])
        canvas = FakeCanvas(initial_scale=50000.0)
        iface = FakeIface(canvas)
        plugin = ZoomToPredefinedScalePlugin(iface)
        plugin.initGui()
        plugin._action.trigger()  # lock

        plugin.unload()

        self.assertEqual(iface.toolbar_actions, [])
        self.assertTrue(all(len(a) == 0 for a in iface.menu_actions.values()))

        # The controller must be fully torn down: further zoom events and
        # project-scale changes are silently ignored, not raise.
        canvas.simulate_native_zoom(12345.0)
        self.assertEqual(canvas.scale(), 12345.0)
        _configure_scales([1, 2, 3])

    def test_reload_does_not_create_duplicate_toolbar_actions(self):
        iface = FakeIface()

        plugin_a = ZoomToPredefinedScalePlugin(iface)
        plugin_a.initGui()
        self.assertEqual(len(iface.toolbar_actions), 1)
        plugin_a.unload()
        self.assertEqual(len(iface.toolbar_actions), 0)

        plugin_b = ZoomToPredefinedScalePlugin(iface)
        plugin_b.initGui()
        self.assertEqual(len(iface.toolbar_actions), 1)
        plugin_b.unload()
        self.assertEqual(len(iface.toolbar_actions), 0)


if __name__ == "__main__":
    unittest.main()
