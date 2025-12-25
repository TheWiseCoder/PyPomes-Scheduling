import re
import sys
from collections.abc import Callable
from datetime import datetime
from logging import Logger
from pypomes_core import (
    APP_PREFIX, TZ_LOCAL, env_get_int, exc_format
)
from typing import Any, Final
from zoneinfo import ZoneInfo

from .threaded_scheduler import _ThreadedScheduler

SCHEDULER_RETRY_INTERVAL: Final[int] = env_get_int(key=f"{APP_PREFIX}_SCHEDULER_RETRY_INTERVAL",
                                                   def_value=10)
__DEFAULT_BADGE: Final[str] = "__default__"
__REGEX_VERIFY_CRON: Final[re.Pattern] = re.compile(
    r"^("
    r"@(annually|yearly|monthly|weekly|daily|hourly|reboot)|"
    r"@every\s+\d+(ns|us|µs|ms|s|m|h)|"
    r"("
    # seconds: 0-59
    r"((\*|([0-5]?\d)(-[0-5]?\d)?)(/[0-5]?\d)?"
    r"(,([0-5]?\d)(-[0-5]?\d)?(/[0-5]?\d)?)*)\s+"

    # minutes: 0-59
    r"((\*|([0-5]?\d)(-[0-5]?\d)?)(/[0-5]?\d)?"
    r"(,([0-5]?\d)(-[0-5]?\d)?(/[0-5]?\d)?)*)\s+"

    # hours: 0-23
    r"((\*|([01]?\d|2[0-3])(-([01]?\d|2[0-3]))?)(/[01]?\d|2[0-3])?"
    r"(,([01]?\d|2[0-3])(-([01]?\d|2[0-3]))?(/[01]?\d|2[0-3])?)*)\s+"

    # day of month: 1-31 or '?'
    r"((\*|\?|([1-9]|[12]\d|3[01])(-([1-9]|[12]\d|3[01]))?)(/[1-9]|[12]\d|3[01])?"
    r"(,([1-9]|[12]\d|3[01])(-([1-9]|[12]\d|3[01]))?(/[1-9]|[12]\d|3[01])?)*)\s+"

    # month: 1-12 or JAN-DEC
    r"((\*|([1-9]|1[0-2]|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"
    r"(-([1-9]|1[0-2]|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC))?)"
    r"(/[1-9]|1[0-2])?"
    r"(,([1-9]|1[0-2]|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)"
    r"(-([1-9]|1[0-2]|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC))?"
    r"(/[1-9]|1[0-2])?)*)\s+"

    # day of week: 0-6 or SUN-SAT or '?'
    r"((\*|\?|([0-6]|SUN|MON|TUE|WED|THU|FRI|SAT)"
    r"(-([0-6]|SUN|MON|TUE|WED|THU|FRI|SAT))?)"
    r"(/[0-6])?"
    r"(,([0-6]|SUN|MON|TUE|WED|THU|FRI|SAT)"
    r"(-([0-6]|SUN|MON|TUE|WED|THU|FRI|SAT))?"
    r"(/[0-6])?)*)"

    # year: 1970-2099 (optional)
    r"(\s+(\*|19[7-9]\d|20\d\d)(-(19[7-9]\d|20\d\d))?)?"
    r")"
    r")$"
)

# dict holding the schedulers created:
#   <{ <badge-1>: <scheduler-instance-1>,
#     ...
#     <badge-n>: <scheduler-instance-n>
#   }>
__schedulers: dict[str, Any] = {}


def scheduler_create(badge: str = __DEFAULT_BADGE,
                     is_daemon: bool = True,
                     timezone: ZoneInfo = TZ_LOCAL,
                     retry_interval: int = SCHEDULER_RETRY_INTERVAL,
                     errors: list[str] = None) -> bool:
    """
    Create the threaded job scheduler.

    This is a wrapper around the package *APScheduler*.

    :param is_daemon: indicates whether this thread is a daemon thread (defaults to *True*)
    :param badge: badge identifying the scheduler (defaults to __DEFAULT_BADGE)
    :param timezone: the timezone to be used (defaults to the configured local timezone)
    :param retry_interval: interval between retry attempts, in minutes (defaults to the configured value)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the scheduler was created, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    # has the scheduler been created ?
    if __get_scheduler(badge=badge,
                       must_exist=False,
                       errors=errors) is None:
        # no, create it
        try:
            __schedulers[badge] = _ThreadedScheduler(timezone=timezone,
                                                     retry_interval=retry_interval)
            if is_daemon:
                __schedulers[badge].daemon = True
            result = True
        except Exception as e:
            exc_err: str = exc_format(exc=e,
                                      exc_info=sys.exc_info())
            err_msg: str = f"Error creating the job scheduler '{badge}': {exc_err}"
            if _ThreadedScheduler.LOGGER:
                _ThreadedScheduler.LOGGER.error(msg=err_msg)
            if isinstance(errors, list):
                errors.append(err_msg)

    return result


def scheduler_destroy(badge: str = __DEFAULT_BADGE) -> None:
    """
    Destroy the scheduler identified by *badge*. *Noop* if the scheduler does not exist.

    :param badge:  badge identifying the scheduler (defaults to __DEFAULT_BADGE)
    """
    # retrieve the scheduler
    scheduler: _ThreadedScheduler = __schedulers.get(badge)

    # stop and discard the scheduler
    if scheduler:
        scheduler.stop()
        __schedulers.pop(badge)


def scheduler_assert_access(errors: list[str] | None) -> bool:
    """
    Determine whether accessing a scheduler is possible.

    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if accessing succeeded, *False* otherwise
    """
    badge: str = "__temp__"
    result: bool = scheduler_create(badge=badge,
                                    errors=errors)
    if result:
        scheduler_destroy(badge=badge)
    return result


def scheduler_start(badge: str = __DEFAULT_BADGE,
                    errors: list[str] = None) -> bool:
    """
    Start the scheduler.

    :param badge: badge identifying the scheduler (defaults to __DEFAULT_BADGE)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the scheduler has been started, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    # retrieve the scheduler
    scheduler: _ThreadedScheduler = __get_scheduler(badge=badge,
                                                    errors=errors)
    if scheduler:
        try:
            scheduler.start()
            result = True
        except Exception as e:
            exc_err: str = exc_format(exc=e,
                                      exc_info=sys.exc_info())
            err_msg: str = f"Error starting the scheduler '{badge}': {exc_err}"
            if _ThreadedScheduler.LOGGER:
                _ThreadedScheduler.LOGGER.error(msg=err_msg)
            if isinstance(errors, list):
                errors.append(err_msg)

    return result


def scheduler_stop(badge: str = __DEFAULT_BADGE,
                   errors: list[str] = None) -> bool:
    """
    Stop the scheduler.

    :param badge: badge identifying the scheduler (defaults to __DEFAULT_BADGE)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the scheduler has been stopped, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    # retrieve the scheduler
    scheduler: _ThreadedScheduler = __get_scheduler(badge=badge,
                                                    errors=errors)
    if scheduler:
        scheduler.stop()
        result = True

    return result


def scheduler_add_job(job: Callable,
                      job_id: str,
                      job_name: str,
                      job_cron: str = None,
                      job_start: datetime = None,
                      job_args: tuple = None,
                      job_kwargs: dict = None,
                      badge: str = __DEFAULT_BADGE,
                      errors: list[str] = None) -> bool:
    """
    Schedule the job identified as *job_id* and named as *job_name*.

    The scheduling is performed with the *CRON* expression *job_cron*, starting at the timestamp *job_start*.
    Positional arguments for the scheduled job may be provided in *job_args*.
    Named arguments for the scheduled job may be provided in *job_kwargs*.

    :param job: the job to be scheduled
    :param job_id: the id of the job to be scheduled
    :param job_name: the name of the job to be scheduled
    :param job_cron: the CRON expression
    :param job_start: the start timestamp
    :param job_args: the positional arguments for the scheduled job
    :param job_kwargs: the named arguments for the scheduled job
    :param badge: badge identifying the scheduler (defaults to __DEFAULT_BADGE)
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the job was successfully scheduled, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    # retrieve the scheduler
    scheduler: _ThreadedScheduler = __get_scheduler(badge=badge,
                                                    errors=errors)
    if scheduler:
        result = __scheduler_add_job(scheduler=scheduler,
                                     job=job,
                                     job_id=job_id,
                                     job_name=job_name,
                                     job_cron=job_cron,
                                     job_start=job_start,
                                     job_args=job_args,
                                     job_kwargs=job_kwargs,
                                     errors=errors)
    return result


def scheduler_add_jobs(jobs: list[tuple[Callable, str, str, str, datetime, tuple, dict]],
                       badge: str = __DEFAULT_BADGE,
                       errors: list[str] = None) -> int:
    r"""
    Schedule the jobs described in *jobs*, starting at the given timestamp.

    Each element in the job list is a *tuple* with the following job data items:
        - Callable function: the function to be invoked by the scheduler (*Callable*)
        - job id: the id of the job to be started (*str*)
        - job name: the name of the job to be started (*str*)
        - start timestamp: the date and time to start scheduling the job (*datetime*)
        - job args: the positional arguments (*\*args*) to be passed to the job (*tuple*)
        - job kwargs: the named arguments (*\*\*kwargs*) to be passed to the job (*dict*)
    Only the first three data items are required.

    :param jobs: list of tuples describing the jobs to be scheduled
    :param badge: badge identifying the scheduler (defaults to __DEFAULT_BADGE)
    :param errors: incidental error messages (might be a non-empty list)
    :return: the number of jobs effectively scheduled
    """
    # initialize the return variable
    result: int = 0

    # retrieve the scheduler
    scheduler: _ThreadedScheduler = __get_scheduler(badge=badge,
                                                    errors=errors)
    if scheduler:
        # traverse the job list and attempt the scheduling
        for job in jobs:
            # process the required parameters
            job_function: Callable = job[0]
            job_id: str = job[1]
            job_name: str = job[2]

            # process the optional arguments
            job_cron: str = job[3] if len(job) > 3 else None
            job_start: datetime = job[4] if len(job) > 4 else None
            job_args: tuple = job[5] if len(job) > 5 else None
            job_kwargs: dict = job[6] if len(job) > 6 else None

            # add to the return variable, if scheduling was successful
            if __scheduler_add_job(scheduler=scheduler,
                                   job=job_function,
                                   job_id=job_id,
                                   job_name=job_name,
                                   job_cron=job_cron,
                                   job_start=job_start,
                                   job_args=job_args,
                                   job_kwargs=job_kwargs,
                                   errors=errors):
                result += 1

    return result


def scheduler_set_logger(logger: Logger) -> None:
    """
    Establish the class logger.

    :param logger: the class logger
    """
    _ThreadedScheduler.LOGGER = logger


def __get_scheduler(badge: str,
                    must_exist: bool = True,
                    errors: list[str] = None) -> _ThreadedScheduler:
    """
    Retrieve the scheduler identified by *badge*.

    :param badge: badge identifying the scheduler
    :param must_exist: True if scheduler must exist
    :param errors: incidental error messages (might be a non-empty list)
    :return: the scheduler retrieved, or *None* otherwise
    """
    result: _ThreadedScheduler = __schedulers.get(badge)
    if must_exist and not result:
        err_msg: str = f"Job scheduler '{badge}' has not been created"
        if _ThreadedScheduler.LOGGER:
            _ThreadedScheduler.LOGGER.error(msg=err_msg)
        if isinstance(errors, list):
            errors.append(err_msg)

    return result


def __scheduler_add_job(scheduler: _ThreadedScheduler,
                        job: Callable,
                        job_id: str,
                        job_name: str,
                        job_cron: str = None,
                        job_start: datetime = None,
                        job_args: tuple = None,
                        job_kwargs: dict = None,
                        errors: list[str] = None) -> bool:
    r"""
    Use *scheduler* to schedule the job identified as *job_id* and named as *job_name*.

    The scheduling is performed with the *CRON* expression *job_cron*, starting at the timestamp *job_start*.
    Positional arguments for the scheduled job may be provided in *job_args*.
    Named arguments for the scheduled job may be provided in *job_kwargs*.

    A valid *CRON* expression has the syntax *[<sec>] <min> <hour> <day> <month> <day-of-week> [<year>]*,
    where *sec* and <year> are optional, and can include:
      - numbers (e.g. '5')
      - ranges (e.g. '1-5')
      - lists (e.g. '1,2,3')
      - steps (e.g. '*/15')
      - mnemonics (e.g. 'JAN', 'SUN')
      - wildcards ('*')
      - ignored ('?' - *<day-of-week>* and *<day-of-month>*)
    According to its length, the *CRON* expression may contain:
      - 5: *<min> <hour> <day> <month> <day-of-week>*               (*<sec>* and *<year>* not specified)
      - 6: *<sec> <min> <hour> <day> <month> <day-of-week>*         (*<year>* not specified)
      - 7: *<sec> <min> <hour> <day> <month> <day-of-week> <year>*

    :param scheduler: the scheduler to use
    :param job: the job to be scheduled
    :param job_id: the id of the job to be scheduled
    :param job_name: the name of the job to be scheduled
    :param job_cron: the CRON expression
    :param job_start: the date and time to start scheduling the job
    :param job_args: the positional arguments (*\*args*) to be passed to the job
    :param job_kwargs: the named arguments (*\*\*kwargs*) to be passed to the job
    :param errors: incidental error messages (might be a non-empty list)
    :return: *True* if the job was successfully scheduled, *False* otherwise
    """
    # initialize the return variable
    result: bool = False

    # validate the CRON expression
    err_msg: str | None = None
    cron_expr: str | None = None
    if job_cron:
        if len(job_cron.split()) == 5:
            cron_expr = f"* {job_cron}"
        else:
            cron_expr = job_cron
        if not __REGEX_VERIFY_CRON.fullmatch(string=cron_expr):
            # bad CRON expression, report the error
            err_msg = f"Invalid CRON expression: '{job_cron}'"
            if _ThreadedScheduler.LOGGER:
                _ThreadedScheduler.LOGGER.error(msg=err_msg)

    # proceed with the scheduling
    if not err_msg:
        try:
            scheduler.schedule_job(job=job,
                                   job_id=job_id,
                                   job_name=job_name,
                                   job_cron=cron_expr,
                                   job_start=job_start,
                                   job_args=job_args,
                                   job_kwargs=job_kwargs)
            result = True
        except Exception as e:
            err_msg = (f"Error scheduling the job '{job_name}', id '{job_id}', "
                       f"with CRON '{job_cron}': {exc_format(e, sys.exc_info())}")
            if _ThreadedScheduler.LOGGER:
                _ThreadedScheduler.LOGGER.error(msg=err_msg)

    if err_msg and isinstance(errors, list):
        errors.append(err_msg)

    return result
