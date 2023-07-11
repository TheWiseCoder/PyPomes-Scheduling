from datetime import datetime
from pypomes_core.env_pomes import APP_PREFIX, env_get_str, env_get_int
from pypomes_core.exception_pomes import exc_format
from typing import Final
import logging
import pytz
import re
import sys
from .threaded_scheduler import __ThreadedScheduler

__REGEX_VERIFY_CRON: Final[str] = "/(@(annually|yearly|monthly|weekly|daily|hourly|reboot))|" \
                                  "(@every (\d+(ns|us|µs|ms|s|m|h))+)|((((\d+,)+\d+|(\d+(\/|-)\d+)|\d+|\*) ?){5,7})"

__scheduler: __ThreadedScheduler


def scheduler_create(errors: list[str], timezone: pytz.BaseTzInfo,
                     retry_interval: int, logger: logging.Logger = None) -> bool:
    """
    Create the threaded job scheduler. This is a wrapper around the package *apscheduler*.

    :param errors: Resulting errors, if any
    :param timezone: The timezone to be used
    :param retry_interval: Interval between retry attempts, in minutes
    :param logger: Optional logger object
    :return: True if scheduler was created, or False if an error prevented its creation
    """
    global __scheduler
    # inicialize the return variable
    result: bool = False

    try:
        __scheduler = __ThreadedScheduler(timezone, retry_interval, logger)
        __scheduler.daemon = True
        result = True
    except Exception as e:
        errors.append(f"Error creating the job scheduler: {exc_format(e, sys.exc_info())}")

    return result


def scheduler_schedule(errors: list[str],
                       jobs: list[tuple[callable, str, str, tuple, str]], start: datetime) -> int:
    """
    Schedule the jobs in *jobs*, starting at the given *start*. Each element in the job list is a *tuple* with
    the corresponding job data: *(callable function, job id, job name, job arguments, CRON expression)*.

    :param errors: Resulting errors, if any
    :param jobs: List of tuples with jobs to schedule
    :param start: Optional start timestamp for the scheduler
    :return: The number of jobs effectively scheduled
    """
    global __scheduler
    # inicializa a variável de retorno
    result: int = 0

    # traverse the job list and do the scheduling
    for job in jobs:

        # is it a valid CRON expression ?
        if re.search(__REGEX_VERIFY_CRON, job[4]) is None:
            # no, report the error
            errors.append(f"Invalid CRON expression: '{job[4]}'")
        else:
            # yes, proceed with the scheduling
            try:
                __scheduler.schedule_job(job[0], job[1], job[2], job[4], job[3], start)
                result += 1
            except Exception as e:
                errors.append(f"Error scheduling the job '{job[2]}', id '{job[1]}', "
                              f"with CRON '{job[3]}': {exc_format(e, sys.exc_info())}")

    return result


def scheduler_start():
    """
    Start the scheduler.
    """
    global __scheduler
    __scheduler.start()


def scheduler_stop():
    """
    Stop the scheduler.
    """
    global __scheduler
    __scheduler.stop()
