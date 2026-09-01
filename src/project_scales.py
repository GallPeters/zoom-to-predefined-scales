"""Reads the *actual* predefined map scales configured on a QGIS project.

Predefined scales live on ``QgsProject.viewSettings()``
(:class:`QgsProjectViewSettings`), configured by the user in
*Project -> Properties -> View Settings -> Project predefined scales*:

    * ``useProjectScales() -> bool``   whether the project's own scale list
      should be used at all (the checkbox in that dialog).
    * ``mapScales() -> list[float]``   the configured scale denominators.
    * ``mapScalesChanged``             signal emitted when either changes.

This module never stores its own scale list and never mutates the project;
it only reads and normalizes what is already there.
"""

from __future__ import annotations

from qgis.core import QgsProject

from .scale_utils import normalize_scales


class ScaleAvailability:
    """Outcome of asking the project for its predefined scales."""

    #: Predefined scales are enabled and at least one usable scale exists.
    ENABLED_WITH_SCALES = "enabled_with_scales"
    #: The "use predefined scales" option is turned off in the project.
    DISABLED = "disabled"
    #: Enabled, but the configured scale list is empty (or all invalid).
    ENABLED_EMPTY = "enabled_empty"
    #: No project / no view settings available at all.
    NO_PROJECT = "no_project"


def get_project_predefined_scales(project=None):
    """Return ``(availability, scales)`` for *project* (or the current
    project if omitted).

    ``scales`` is always an ascending, de-duplicated tuple -- empty unless
    ``availability`` is :attr:`ScaleAvailability.ENABLED_WITH_SCALES`.
    """
    if project is None:
        project = QgsProject.instance()
    if project is None:
        return ScaleAvailability.NO_PROJECT, ()

    view_settings = project.viewSettings()
    if view_settings is None:
        return ScaleAvailability.NO_PROJECT, ()

    if not view_settings.useProjectScales():
        return ScaleAvailability.DISABLED, ()

    scales = normalize_scales(view_settings.mapScales())
    if not scales:
        return ScaleAvailability.ENABLED_EMPTY, ()

    return ScaleAvailability.ENABLED_WITH_SCALES, scales
