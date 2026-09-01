"""Plugins -> Zoom to Predefined Scales -> Settings...

For now the only thing this dialog offers is a "Run Tests" button - shown
only when a ``tests/`` folder can actually be found next to this install
(a development checkout, or an install that was packaged together with its
tests) - which runs the plugin's own test suite and reports the result in a
separate results window with a Close button.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QPushButton,
)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Zoom to Predefined Scales - Settings")

        layout = QVBoxLayout(self)

        tests_dir = self._tests_directory()
        if tests_dir is not None:
            dev_group = QGroupBox("Developer", self)
            dev_layout = QVBoxLayout(dev_group)
            self.btn_run_tests = QPushButton("Run Tests", dev_group)
            self.btn_run_tests.setToolTip(
                f"Run the test suite in:\n{tests_dir}\n\n"
                "Your currently open project's predefined-scale settings are "
                "snapshotted before the run and restored exactly afterwards, "
                "even if a test fails, so nothing about it is left changed. "
                "The window stays open and responsive throughout."
            )
            self.btn_run_tests.clicked.connect(self._run_tests)
            dev_layout.addWidget(self.btn_run_tests)
            layout.addWidget(dev_group)
        else:
            self.btn_run_tests = None
            layout.addWidget(
                QLabel(
                    "No developer options are available in this installation "
                    "(no tests/ folder was found next to the plugin).",
                    self,
                )
            )

        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.clicked.connect(self.accept)
        layout.addWidget(buttons)

        self.resize(420, 220)

    # ------------------------------------------------------------------ #
    # Developer: run the test suite
    # ------------------------------------------------------------------ #

    @staticmethod
    def _tests_directory() -> Optional[Path]:
        """The tests/ folder, if one is findable next to this install.

        Checked in order:

        * nested inside this same plugin folder, e.g. ``tests/`` copied in
          alongside ``zoom_to_predefined_scale.py`` - the natural result of
          installing the plugin *with* its tests (exactly what a release
          zip built for the QGIS plugin portal contains), not just a
          development checkout;
        * a sibling of ``src/`` one level up - the git-checkout layout. This
          file lives at ``<repo>/src/settings_dialog.py`` there.

        A normal end-user install that only ships ``src/``'s contents, with
        no ``tests/`` anywhere nearby, matches neither and returns ``None``.
        """
        here = Path(__file__).resolve().parent
        for candidate in (here / "tests", here.parent / "tests"):
            if (candidate / "run_all.py").is_file():
                return candidate
        return None

    def _run_tests(self, *, _run_all_override=None) -> None:
        """Run the test suite and show a pass/fail summary plus the full log.

        ``_run_all_override`` is keyword-only, deliberately: this method is
        connected to ``btn_run_tests.clicked``, whose ``clicked(bool
        checked)`` signal PyQt auto-forwards into a slot's own positional
        parameters. A plain positional parameter here would mean a normal
        click passes that ``bool`` straight into ``_run_all_override``,
        crashing the moment "Run Tests" is actually clicked. Keyword-only is
        invisible to that auto-forwarding, so a real click still calls this
        with no arguments at all, exactly as intended.

        ``_run_all_override`` is a testing-only seam: pass a fake module
        (anything with a ``main()``) to exercise this method's own control
        flow without paying for a real, recursive run of the whole suite. It
        exists because this method itself forces a fresh re-import of
        ``tests`` on every call (see below) - a plain
        ``mock.patch("tests.run_all.main", ...)`` would just be undone by
        that re-import. Left ``None`` for real use.

        Run synchronously - the only option: everything here (including the
        results window) only runs safely on the main GUI thread.
        ``_ResponsiveTestResult`` below processes events after every
        individual test, keeping the window repainting and responsive
        throughout a run that can take a little while.
        """
        tests_dir = self._tests_directory()
        if tests_dir is None:
            QMessageBox.information(
                self,
                "Run Tests",
                "No tests/ folder found next to the plugin - this is only "
                "available when running from a development checkout, or an "
                "install that was packaged together with its tests.",
            )
            return

        self.btn_run_tests.setEnabled(False)
        self.btn_run_tests.setText("Running...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()  # show the label change before the run blocks

        result = None
        log_text = ""
        try:
            import io
            import sys

            repo_root = str(tests_dir.parent)
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)

            if _run_all_override is not None:
                run_all = _run_all_override
            else:
                # Force a fresh import of the whole tests/ package, and of
                # the plugin's own source modules under the test-only
                # "_ztps_plugin" alias every test module imports them
                # through (see tests/__init__.py) - rather than reusing
                # whatever Python already has cached in sys.modules. A QGIS
                # session commonly outlives many "Run Tests" clicks, and
                # without this, a fix to any test file - or to this
                # plugin's own code - would keep running the STALE, already
                # -imported version until QGIS itself restarts: once
                # cached, a plain `from tests import run_all` never looks
                # at any of those files again. Never touches the REAL, live
                # plugin instance QGIS itself already loaded - that lives
                # under its own real package name, an entirely separate set
                # of module objects from this alias.
                for name in list(sys.modules):
                    if (
                        name == "tests"
                        or name.startswith("tests.")
                        or name == "_ztps_plugin"
                        or name.startswith("_ztps_plugin.")
                    ):
                        del sys.modules[name]
                from tests import run_all  # only importable in a dev checkout

            class _ResponsiveTestResult(unittest.TextTestResult):
                """Keeps the application repainting and responsive during a
                long run - see this method's own docstring."""

                def startTest(self, test) -> None:  # noqa: N802 (unittest API)
                    super().startTest(test)
                    QApplication.processEvents()

            buffer = io.StringIO()
            try:
                result = run_all.main(verbosity=2, stream=buffer, resultclass=_ResponsiveTestResult)
            except TypeError:
                # An installed tests/run_all.py that predates the
                # resultclass parameter, or a version of this module Python
                # already had cached in sys.modules from earlier in the
                # same session. Falls back to a plain run rather than
                # crashing outright; only the responsiveness during it is
                # lost.
                buffer = io.StringIO()
                result = run_all.main(verbosity=2, stream=buffer)
            log_text = buffer.getvalue()
        except Exception:
            # The full traceback, not just str(exc): a bare exception
            # message gives no clue which call in the chain actually
            # raised it, or from which module - exactly the information
            # needed to diagnose an environment-specific failure.
            import traceback

            log_text = f"Could not run the test suite:\n{traceback.format_exc()}"
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_run_tests.setEnabled(True)
            self.btn_run_tests.setText("Run Tests")

        self._show_test_results(result, log_text)

    def _show_test_results(self, result, log_text: str) -> None:
        """A small dialog: a coloured pass/fail summary, then the full log."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Test Results")
        dialog.resize(760, 500)
        layout = QVBoxLayout(dialog)

        if result is None:
            summary, color = "Could not run the test suite - see the log below.", "#b7791f"
        elif result.wasSuccessful():
            summary, color = f"All {result.testsRun} tests passed.", "#2e7d32"
        else:
            failed = len(result.failures) + len(result.errors)
            summary = f"{failed} of {result.testsRun} tests failed - see the log below."
            color = "#c0392b"

        lbl_summary = QLabel(summary, dialog)
        lbl_summary.setStyleSheet(f"font-weight: bold; color: {color};")
        layout.addWidget(lbl_summary)

        log_view = QPlainTextEdit(dialog)
        log_view.setReadOnly(True)
        log_view.setPlainText(log_text)
        log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        log_view.setFont(font)
        layout.addWidget(log_view)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        buttons.rejected.connect(dialog.reject)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.clicked.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.exec()
