"""Progress reporting abstractions for the pipeline."""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

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


class RichProgressReporter:
    """Progress reporter that uses Rich spinners with elapsed timers."""

    def __init__(self, console: Console) -> None:
        self._console = console

    @contextmanager
    def step(self, spinner: str, color: str) -> Generator[Callable[[str], None]]:
        with Progress(
            SpinnerColumn(spinner_name=spinner),
            TextColumn("{task.description}"),
            TimeElapsedColumn(),
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
