# -*- coding: utf-8 -*-
"""Tests for project_scales.get_project_predefined_scales() against a real
QgsProject (see tests/__init__.py for the qgis.testing bootstrap)."""

import unittest

from qgis.core import QgsProject

from _ztps_plugin.project_scales import ScaleAvailability, get_project_predefined_scales


class ProjectScalesTests(unittest.TestCase):
    def setUp(self):
        # Start every test from a clean slate: no predefined scales.
        QgsProject.instance().clear()

    def test_disabled_when_use_project_scales_is_off(self):
        project = QgsProject.instance()
        project.viewSettings().setMapScales([50000, 25000])
        project.viewSettings().setUseProjectScales(False)

        availability, scales = get_project_predefined_scales(project)

        self.assertEqual(availability, ScaleAvailability.DISABLED)
        self.assertEqual(scales, ())

    def test_enabled_empty_when_scale_list_is_empty(self):
        project = QgsProject.instance()
        project.viewSettings().setMapScales([])
        project.viewSettings().setUseProjectScales(True)

        availability, scales = get_project_predefined_scales(project)

        self.assertEqual(availability, ScaleAvailability.ENABLED_EMPTY)
        self.assertEqual(scales, ())

    def test_enabled_with_scales_returns_normalized_scales(self):
        project = QgsProject.instance()
        project.viewSettings().setMapScales([50000, 100000, 25000, 50000])
        project.viewSettings().setUseProjectScales(True)

        availability, scales = get_project_predefined_scales(project)

        self.assertEqual(availability, ScaleAvailability.ENABLED_WITH_SCALES)
        self.assertEqual(scales, (25000.0, 50000.0, 100000.0))

    def test_defaults_to_current_project_instance_when_none_passed(self):
        project = QgsProject.instance()
        project.viewSettings().setMapScales([10000])
        project.viewSettings().setUseProjectScales(True)

        availability, scales = get_project_predefined_scales()

        self.assertEqual(availability, ScaleAvailability.ENABLED_WITH_SCALES)
        self.assertEqual(scales, (10000.0,))


if __name__ == "__main__":
    unittest.main()
