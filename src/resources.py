"""Icon path helper.

This is deliberately NOT a pyrcc/pyside-rcc *compiled* Qt resource module.
The plugin loads its icons directly from disk (see this same folder and
``zoom_to_predefined_scale.py``), which avoids a build step and can never
drift out of sync with the files actually shipped in the plugin package.

This module just centralises the on-disk icon paths so other code (and
tests) can refer to them by name instead of hard-coding strings. If you
want a real compiled Qt resource instead, see the instructions at the top
of ``resources.qrc``.
"""

import os

_PLUGIN_DIR = os.path.dirname(__file__)

ICON_UNLOCKED = os.path.join(_PLUGIN_DIR, "icon_unlocked.svg")
ICON_LOCKED = os.path.join(_PLUGIN_DIR, "icon_locked.svg")


def qInitResources():  # noqa: N802 - matches the symbol pyrcc/pyside-rcc emit
    """No-op. Present only so code that expects a compiled resource module
    to expose this symbol does not fail to import."""
    return None


def qCleanupResources():  # noqa: N802
    """No-op counterpart to :func:`qInitResources`."""
    return None
