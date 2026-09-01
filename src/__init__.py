"""QGIS plugin package for "Zoom to Predefined Scales".

The import of the actual plugin class is deferred to inside
``classFactory`` (rather than at module level) so that this package can be
imported -- e.g. by the test suite -- without QGIS/PyQt6 being installed.
QGIS itself only ever calls ``classFactory``, never imports the submodule
directly, so this has no effect on normal plugin loading.
"""


def classFactory(iface):
    from .zoom_to_predefined_scale import ZoomToPredefinedScalePlugin

    return ZoomToPredefinedScalePlugin(iface)
