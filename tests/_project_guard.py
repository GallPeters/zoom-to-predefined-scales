# -*- coding: utf-8 -*-
"""Snapshot/restore the active QgsProject's predefined-scale view settings
around a test run.

Several tests deliberately enable/disable "use predefined scales" and
overwrite the project's scale list to get a clean, predictable starting
point - exactly right for a disposable ``qgis.testing`` process, exactly
wrong if this suite is ever run from inside a live QGIS session with the
user's own project open (e.g. via the Settings dialog's "Run Tests"
button). This is the outer safety net: it restores the project's predefined
-scale settings to exactly what they were before the run, regardless of
what any individual test does or whether the run raises.

It is a backstop, not the primary defence - individual tests reset the
project to a clean slate themselves (see each test module's ``setUp``),
rather than relying on this to undo a blunter "leave it however the last
test left it" approach.
"""

from __future__ import annotations

from typing import Callable, TypeVar

T = TypeVar("T")


def guarded_run(run: Callable[[], T]) -> T:
    """Call ``run()``, then restore the active project's predefined-scale
    view settings."""
    from qgis.core import QgsProject

    view_settings = QgsProject.instance().viewSettings()
    original_use_scales = view_settings.useProjectScales()
    original_scales = list(view_settings.mapScales())

    try:
        return run()
    finally:
        view_settings.setMapScales(original_scales)
        view_settings.setUseProjectScales(original_use_scales)
