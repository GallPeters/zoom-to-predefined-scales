# -*- coding: utf-8 -*-
"""Tests for the Settings dialog's "Run Tests" button.

Uses the ``_run_all_override`` testing seam and mocks out
``_show_test_results`` rather than letting it actually open the (modal)
results window - see the docstrings on both for why.
"""

import inspect
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from _ztps_plugin.settings_dialog import SettingsDialog  # noqa: E402


class _FakeResult:
    def __init__(self, testsRun, failures=(), errors=()):
        self.testsRun = testsRun
        self.failures = list(failures)
        self.errors = list(errors)

    def wasSuccessful(self) -> bool:
        return not self.failures and not self.errors


class SettingsDialogTests(unittest.TestCase):
    def test_tests_directory_is_found_in_this_dev_checkout(self):
        # This repository's own tests/ folder is a sibling of src/, where
        # this file lives - exactly the layout _tests_directory() looks for.
        tests_dir = SettingsDialog._tests_directory()
        self.assertIsNotNone(tests_dir)
        self.assertTrue((tests_dir / "run_all.py").is_file())

    def test_run_tests_button_shown_when_tests_directory_is_found(self):
        dialog = SettingsDialog()
        try:
            self.assertTrue(hasattr(dialog, "btn_run_tests"))
            self.assertIsNotNone(dialog.btn_run_tests)
            self.assertEqual(dialog.btn_run_tests.text(), "Run Tests")
        finally:
            dialog.deleteLater()

    def test_run_all_override_is_keyword_only_so_a_real_click_cannot_reach_it(self):
        """Regression: QPushButton.clicked emits clicked(bool checked), and
        PyQt auto-forwards emitted signal arguments into a slot's own
        POSITIONAL parameters. A positional _run_all_override would mean a
        real click passes that bool straight into it instead of leaving it
        at its None default."""
        sig = inspect.signature(SettingsDialog._run_tests)
        param = sig.parameters["_run_all_override"]
        self.assertEqual(param.kind, inspect.Parameter.KEYWORD_ONLY)

    def test_run_tests_passes_the_result_through_and_re_enables_the_button(self):
        dialog = SettingsDialog()
        fake_result = _FakeResult(testsRun=5)
        fake_run_all = mock.Mock(main=mock.Mock(return_value=fake_result))
        try:
            with mock.patch.object(SettingsDialog, "_show_test_results") as mocked_show:
                dialog._run_tests(_run_all_override=fake_run_all)

            fake_run_all.main.assert_called_once()
            mocked_show.assert_called_once()
            self.assertIs(mocked_show.call_args[0][0], fake_result)
            self.assertTrue(dialog.btn_run_tests.isEnabled())
            self.assertEqual(dialog.btn_run_tests.text(), "Run Tests")
        finally:
            dialog.deleteLater()

    def test_run_tests_falls_back_when_run_all_predates_resultclass_param(self):
        """An installed tests/run_all.py without the resultclass parameter
        (or one already cached in sys.modules from before an update) must
        not crash the button outright - it just loses the responsive
        event-pumping during the run."""
        fake_result = _FakeResult(testsRun=3)

        def main(verbosity=2, stream=None, resultclass=None):
            if resultclass is not None:
                raise TypeError("main() got an unexpected keyword argument 'resultclass'")
            return fake_result

        fake_run_all = mock.Mock(main=mock.Mock(side_effect=main))
        dialog = SettingsDialog()
        try:
            with mock.patch.object(SettingsDialog, "_show_test_results") as mocked_show:
                dialog._run_tests(_run_all_override=fake_run_all)

            self.assertEqual(fake_run_all.main.call_count, 2)
            mocked_show.assert_called_once()
            self.assertIs(mocked_show.call_args[0][0], fake_result)
            self.assertTrue(dialog.btn_run_tests.isEnabled())
        finally:
            dialog.deleteLater()

    def test_run_tests_reports_failure_when_suite_raises(self):
        def main(verbosity=2, stream=None, resultclass=None):
            raise RuntimeError("boom")

        fake_run_all = mock.Mock(main=mock.Mock(side_effect=main))
        dialog = SettingsDialog()
        try:
            with mock.patch.object(SettingsDialog, "_show_test_results") as mocked_show:
                dialog._run_tests(_run_all_override=fake_run_all)

            mocked_show.assert_called_once()
            result_arg, log_arg = mocked_show.call_args[0]
            self.assertIsNone(result_arg)
            self.assertIn("boom", log_arg)
            self.assertTrue(dialog.btn_run_tests.isEnabled())
            self.assertEqual(dialog.btn_run_tests.text(), "Run Tests")
        finally:
            dialog.deleteLater()

    def test_summary_text_and_color_for_success_failure_and_error_cases(self):
        dialog = SettingsDialog()
        try:
            # A successful run.
            with mock.patch("_ztps_plugin.settings_dialog.QDialog.exec", return_value=0):
                dialog._show_test_results(_FakeResult(testsRun=4), "log")

            # A run with failures.
            with mock.patch("_ztps_plugin.settings_dialog.QDialog.exec", return_value=0):
                dialog._show_test_results(_FakeResult(testsRun=4, failures=["x"]), "log")

            # The suite could not even be run.
            with mock.patch("_ztps_plugin.settings_dialog.QDialog.exec", return_value=0):
                dialog._show_test_results(None, "could not run")
        finally:
            dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
