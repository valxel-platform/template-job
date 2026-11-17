"""What a run gets: its window, its limits, and a way to stop cleanly."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

from .runs import RunLog
from .settings import Settings


class Stopped(Exception):  # noqa: N818 - a run told to stop, not an error in the work
    """The time limit is near, or the platform asked the pod to stop."""


@dataclass
class Run:
    job: str
    window_start: datetime
    window_end: datetime
    settings: Settings
    runlog: RunLog
    deadline: float  # time.monotonic() value after which the run stops
    dry_run: bool = False
    manual: bool = False
    log: logging.Logger = field(default_factory=lambda: logging.getLogger("job.work"))
    stop_requested: bool = False

    def check(self) -> None:
        """Raise Stopped when the run should end now; call it between items."""
        if self.stop_requested:
            raise Stopped("the platform asked the job to stop")
        if time.monotonic() >= self.deadline:
            raise Stopped("the run reached its time limit")
