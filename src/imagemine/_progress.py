"""Progress reporting abstractions for the pipeline."""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.text import Text

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from rich.console import Console


@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for reporting pipeline step progress."""

    def step(
        self,
        spinner: str,
        color: str,
    ) -> AbstractContextManager[Callable[[str], None]]: ...


class _MinSecElapsedColumn(TimeElapsedColumn):
    """Elapsed time column that shows MM:SS instead of HH:MM:SS."""

    def render(self, task) -> Text:  # noqa: ANN001
        elapsed = task.finished_time if task.finished else task.elapsed
        if elapsed is None:
            return Text("-:--", style="progress.elapsed")
        minutes, seconds = divmod(int(elapsed), 60)
        return Text(f"{minutes}:{seconds:02d}", style="progress.elapsed")


class RichProgressReporter:
    """Progress reporter that uses Rich spinners with elapsed timers."""

    def __init__(self, console: Console) -> None:
        self._console = console

    @contextmanager
    def step(
        self,
        spinner: str,
        color: str,
    ) -> Generator[Callable[[str], None]]:
        with Progress(
            SpinnerColumn(spinner_name=spinner),
            TextColumn("{task.description}"),
            _MinSecElapsedColumn(),
            console=self._console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"[bold {color}]Preparing...", total=None)

            def log(msg: str) -> None:
                progress.update(task, description=f"[bold {color}]{msg}")

            yield log


class NullProgressReporter:
    """No-op progress reporter for silent/JSON modes."""

    @contextmanager
    def step(
        self,
        spinner: str,
        color: str,
    ) -> Generator[Callable[[str], None]]:
        yield lambda _msg: None
