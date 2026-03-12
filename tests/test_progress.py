"""Tests for ProgressReporter implementations."""

from rich.console import Console

from imagemine._progress import NullProgressReporter, RichProgressReporter


def test_null_progress_reporter_yields_callable() -> None:
    reporter = NullProgressReporter()
    with reporter.step("moon", "cyan") as log:
        log("hello")  # should not raise


def test_rich_progress_reporter_yields_callable() -> None:
    console = Console(quiet=True)
    reporter = RichProgressReporter(console)
    with reporter.step("moon", "cyan") as log:
        log("Generating...")  # should not raise
