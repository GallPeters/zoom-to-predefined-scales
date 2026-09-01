# -*- coding: utf-8 -*-
"""Unit tests for the core scale-selection algorithm (scale_utils.py).

Pure logic - no live QgsProject/QgsMapCanvas involved - but still imported
through the synthetic ``_ztps_plugin`` package (see tests/__init__.py) for
consistency with the rest of the suite.
"""

import unittest

from _ztps_plugin.scale_utils import (
    RELATIVE_TOLERANCE,
    is_close,
    nearest_scale,
    next_scale,
    normalize_scales,
)

SCALES_UNSORTED = [100000, 50000, 25000, 10000]
SCALES = normalize_scales(SCALES_UNSORTED)  # ascending: (10000, 25000, 50000, 100000)


class NormalizeScalesTests(unittest.TestCase):
    def test_sorts_ascending(self):
        self.assertEqual(SCALES, (10000.0, 25000.0, 50000.0, 100000.0))

    def test_dedupes_exact_duplicates(self):
        self.assertEqual(
            normalize_scales([50000, 50000, 25000, 25000, 10000]), (10000.0, 25000.0, 50000.0)
        )

    def test_dedupes_near_duplicates_within_tolerance(self):
        self.assertEqual(normalize_scales([50000.0, 50000.0000001]), (50000.0,))

    def test_keeps_distinct_close_but_not_too_close_values(self):
        # 1 part in 1000 apart: clearly distinct, must not be merged.
        self.assertEqual(normalize_scales([50000.0, 50050.0]), (50000.0, 50050.0))

    def test_drops_invalid_entries(self):
        self.assertEqual(
            normalize_scales(
                [50000, 0, -1000, float("nan"), float("inf"), "not a number", None]
            ),
            (50000.0,),
        )

    def test_empty_list(self):
        self.assertEqual(normalize_scales([]), ())
        self.assertEqual(normalize_scales(None), ())

    def test_single_scale(self):
        self.assertEqual(normalize_scales([25000]), (25000.0,))


class NextScaleTests(unittest.TestCase):
    """The core zoom-direction behaviour."""

    def test_zoom_in_from_between_scales_selects_next_smaller(self):
        # current ~40000 sits between 25000 and 50000.
        self.assertEqual(next_scale(SCALES, 40000, zoom_in=True), 25000.0)

    def test_zoom_out_from_between_scales_selects_next_larger(self):
        self.assertEqual(next_scale(SCALES, 40000, zoom_in=False), 50000.0)

    def test_zoom_in_from_exact_predefined_scale_moves_to_next_smaller(self):
        # Matches the worked example in the spec: at exactly 1:50000, zoom
        # in goes to 1:25000.
        self.assertEqual(next_scale(SCALES, 50000, zoom_in=True), 25000.0)

    def test_zoom_out_from_exact_predefined_scale_moves_to_next_larger(self):
        # At exactly 1:50000, zoom out goes to 1:100000.
        self.assertEqual(next_scale(SCALES, 50000, zoom_in=False), 100000.0)

    def test_zoom_in_respects_floating_point_tolerance_at_exact_scale(self):
        nearly_50000 = 50000.0 * (1 + RELATIVE_TOLERANCE / 10)
        self.assertEqual(next_scale(SCALES, nearly_50000, zoom_in=True), 25000.0)

    def test_zoom_out_beyond_largest_scale_clamps_to_largest(self):
        # Current scale is more zoomed out than any predefined scale.
        self.assertEqual(next_scale(SCALES, 500000, zoom_in=False), 100000.0)

    def test_zoom_in_beyond_largest_scale_moves_to_nearest_boundary(self):
        # First zoom-in step from way outside the range lands on the
        # outermost predefined scale rather than jumping straight to the
        # smallest one.
        self.assertEqual(next_scale(SCALES, 500000, zoom_in=True), 100000.0)

    def test_zoom_in_below_smallest_scale_clamps_to_smallest(self):
        self.assertEqual(next_scale(SCALES, 100, zoom_in=True), 10000.0)

    def test_zoom_out_below_smallest_scale_moves_to_nearest_boundary(self):
        self.assertEqual(next_scale(SCALES, 100, zoom_in=False), 10000.0)

    def test_single_predefined_scale_always_returns_it(self):
        single = (25000.0,)
        self.assertEqual(next_scale(single, 10000, zoom_in=True), 25000.0)
        self.assertEqual(next_scale(single, 100000, zoom_in=False), 25000.0)
        self.assertEqual(next_scale(single, 25000, zoom_in=True), 25000.0)

    def test_empty_scale_list_returns_none(self):
        self.assertIsNone(next_scale((), 50000, zoom_in=True))
        self.assertIsNone(next_scale((), 50000, zoom_in=False))

    def test_at_smallest_scale_zooming_in_further_clamps(self):
        self.assertEqual(next_scale(SCALES, 10000, zoom_in=True), 10000.0)

    def test_at_largest_scale_zooming_out_further_clamps(self):
        self.assertEqual(next_scale(SCALES, 100000, zoom_in=False), 100000.0)


class NearestScaleTests(unittest.TestCase):
    """Used when first engaging the lock."""

    def test_picks_closest_in_log_space(self):
        self.assertEqual(nearest_scale(SCALES, 48000), 50000.0)
        self.assertEqual(nearest_scale(SCALES, 30000), 25000.0)

    def test_exact_match(self):
        self.assertEqual(nearest_scale(SCALES, 25000), 25000.0)

    def test_empty_list_returns_none(self):
        self.assertIsNone(nearest_scale((), 50000))

    def test_handles_non_positive_current_scale(self):
        self.assertEqual(nearest_scale(SCALES, 0), SCALES[0])
        self.assertEqual(nearest_scale(SCALES, -5), SCALES[0])


class IsCloseTests(unittest.TestCase):
    def test_exact_equal(self):
        self.assertTrue(is_close(50000.0, 50000.0))

    def test_within_tolerance(self):
        self.assertTrue(is_close(50000.0, 50000.0 * (1 + RELATIVE_TOLERANCE / 10)))

    def test_outside_tolerance(self):
        self.assertFalse(is_close(50000.0, 50100.0))


if __name__ == "__main__":
    unittest.main()
