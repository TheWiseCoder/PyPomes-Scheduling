from .scheduling_pomes import (
    SCHEDULER_RETRY_INTERVAL,
    scheduler_assert_access,
    scheduler_create, scheduler_destroy,
    scheduler_start, scheduler_stop,
    scheduler_add_job, scheduler_add_jobs,
)

__all__ = [
    # scheduling_pomes
    "SCHEDULER_RETRY_INTERVAL",
    "scheduler_assert_access",
    "scheduler_create", "scheduler_destroy",
    "scheduler_start", "scheduler_stop",
    "scheduler_add_job", "scheduler_add_jobs",
]

from importlib.metadata import version
__version__ = version("pypomes_scheduling")
__version_info__ = tuple(int(i) for i in __version__.split(".") if i.isdigit())
