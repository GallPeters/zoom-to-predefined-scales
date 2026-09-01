"""Pure, QGIS-independent helpers for working with predefined map scales.

Everything in this module is plain Python (no ``qgis`` / ``PyQt6`` imports),
so it can be unit tested without a running QGIS process. It knows nothing
about the map canvas or the project -- it only deals with lists of scale
*denominators* (e.g. ``50000.0`` for a map scale of 1:50000).

Scale semantics used throughout:
    * A smaller denominator means the map is *more* zoomed in (1:1,000 is a
      larger-scale, more detailed view than 1:100,000).
    * "zoom in"  -> move towards a smaller denominator.
    * "zoom out" -> move towards a larger denominator.
"""

from __future__ import annotations

import math

# Two scale denominators are treated as "the same" when they differ by less
# than this fraction of their magnitude. This avoids brittle exact
# floating-point comparisons (e.g. 50000.0 vs 49999.999999998) while still
# being far tighter than any gap a user would realistically configure
# between two distinct predefined scales.
RELATIVE_TOLERANCE = 1e-6


def is_close(a: float, b: float, rel_tol: float = RELATIVE_TOLERANCE) -> bool:
    """Return True if scale denominators *a* and *b* are close enough to be
    considered the same predefined scale."""
    if a == b:
        return True
    return abs(a - b) <= rel_tol * max(abs(a), abs(b))


def normalize_scales(scales) -> tuple:
    """Return *scales* as an ascending, de-duplicated tuple of positive
    finite floats.

    Invalid entries (non-numeric, non-positive, NaN/inf) are dropped
    defensively rather than raising, since this data ultimately comes from
    project files that could be hand-edited or corrupted.
    """
    cleaned = []
    for value in scales or ():
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value) or value <= 0:
            continue
        cleaned.append(value)

    cleaned.sort()

    deduped = []
    for value in cleaned:
        if deduped and is_close(deduped[-1], value):
            continue
        deduped.append(value)
    return tuple(deduped)


def nearest_scale(scales, current_scale):
    """Return the entry of ascending *scales* closest to *current_scale*.

    Distance is measured in log-space so that "closest" matches how zoom
    levels are perceived: the jump from 1:1,000 to 1:2,000 is considered as
    significant as the jump from 1:100,000 to 1:200,000.

    Returns ``None`` if *scales* is empty.
    """
    if not scales:
        return None
    if current_scale is None or current_scale <= 0:
        return scales[0]

    log_current = math.log(current_scale)
    return min(scales, key=lambda s: abs(math.log(s) - log_current))


def next_scale(scales, current_scale, zoom_in):
    """Determine which predefined scale a single zoom step should land on.

    Args:
        scales: ascending, de-duplicated sequence of scale denominators
            (see :func:`normalize_scales`).
        current_scale: the scale denominator the lock last settled on (or
            the canvas' current scale, if no lock reference exists yet).
        zoom_in: True to move towards a smaller denominator (zoom in),
            False to move towards a larger one (zoom out).

    Behaviour:
        * zoom in  -> the *largest* predefined scale strictly smaller than
          ``current_scale``; if none exists, clamp to the smallest
          available scale (already as zoomed-in as the project allows).
        * zoom out -> the *smallest* predefined scale strictly larger than
          ``current_scale``; if none exists, clamp to the largest available
          scale (already as zoomed-out as the project allows).

    Returns ``None`` if *scales* is empty.
    """
    if not scales:
        return None
    if len(scales) == 1:
        return scales[0]

    if zoom_in:
        candidates = [s for s in scales if s < current_scale and not is_close(s, current_scale)]
        return max(candidates) if candidates else scales[0]

    candidates = [s for s in scales if s > current_scale and not is_close(s, current_scale)]
    return min(candidates) if candidates else scales[-1]
