import pytz
import re
import sys
from datetime import datetime
from logging import Logger
from pypomes_core import APP_PREFIX, TIMEZONE_LOCAL, env_get_int, exc_format
from typing import Any, Final

from .threaded_scheduler import _ThreadedScheduler

SCHEDULER_RETRY_INTERVAL: Final[int] = env_get_int(key=f"{APP_PREFIX}_SCHEDULER_RETRY_INTERVAL",
                                                   def_value=10)

__DEFAULT_BADGE: Final[str] = "__default__"

# ruff: noqa: W605
__REGEX_VERIFY_CRON: Final[str] = (
    "/(@(annually|yearly|monthly|weekly|daily|hourly|reboot))|"
    "(@every (\d+(ns|us|µs|ms|s|m|h))+)|((((\d+,)+\d+|(\d+(\/|-)\d+)|\d+|\*) ?){5,7})"
)

# dict holding the schedulers created:
#   <{ <badge-1>: <scheduler-instance-1>,
#     ...
#     <badge-n>: <scheduler-instance-n>
#   }>
__schedulers: dict[str, Any] = {}


def scheduler_create(errors: list[str] | None,
                     badge: str = __DEFAULT_BADGE,
                     is_daemon: bool = True,
                     timezone: pytz.BaseTzInfo = TIMEZONE_LOCAL,
                     retry_interval: int = SCHEDULER_RETRY_INTERVAL,
                     logger: Logger = None) -> bool:
    """
    Create the threaded job scheduler.

    This is a wrapper around the package *APScheduler*.

    :param errors: incidental errors
    :param is_daemon: indicates whether this thread is a daemon thread (defaults to True)
    :param badge: badge identifying the scheduler (defaults to __DEFAULT_BADGE)
    :param timezone: the timezone to be used (defaults to the configured local timezone)
    :param retry_interval: interval between retry attempts, in minutes (defaults to the configured value)
    :param logger: optional logger for logging the scheduler's operations
    :return: True if the scheduler was created, or False otherwise
    """
    # inicialize the return variable
    result: bool = False

    # has the scheduler been created ?
    if __get_scheduler(errors=errors,
                       badge=badge,
                       must_exist=False,
                       logger=logger) is None:
        # no, create it
        try:
            __schedulers[badge] = _ThreadedScheduler(timezone=timezone,
                                                     retry_interval=retry_interval,
                                                     logger=logger)
            if is_daemon:
                __schedulers[badge].daemon = True
            result = True
        except Exception as e:
            exc_err: str = exc_format(exc=e,
                                      exc_info=sys.exc_info())
            err_msg: str = (
                f"Error creating the job scheduler '{badge}': {exc_err}"
            )
            if logger:
                logger.error(msg=err_msg)
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

    # does the scheduler exist ?
    if scheduler:
        # yes, stop and discard it
        scheduler.stop()
        __schedulers.pop(badge)


def scheduler_start(errors: list[str] | None,
                    badge: str = __DEFAULT_BADGE) -> bool:
    """
    Start the scheduler.

    :param errors: incidental errors
    :param badge: badge identifying the scheduler (defaults to __DEFAULT_BADGE)
    :return: True if the scheduler has been started, or False otherwise
    """
    # initialize the return variable
    result: bool = False

    # retrieve the scheduler
    scheduler: _ThreadedScheduler = __get_scheduler(errors=errors,
                                                    badge=badge)

    # proceed, if the scheduler was retrieved
    if scheduler:
        try:
            scheduler.start()
            result = True
        except Exception as e:
            exc_err: str = exc_format(exc=e,
                                      exc_info=sys.exc_info())
            err_msg: str = (
                f"Error starting the scheduler '{badge}': {exc_err}"
            )
            if scheduler.logger:
                scheduler.logger.error(msg=err_msg)
            if isinstance(errors, list):
                errors.append(err_msg)

    return result


def scheduler_stop(errors: list[str],
                   badge: str = __DEFAULT_BADGE) -> bool:
    """
    Stop the scheduler.

    :param errors: incidental errors
    :param badge: badge identifying the scheduler (defaults to __DEFAULT_BADGE)
    :return: True if the scheduler has been stopped, or False otherwise
    """
    # initialize the return variable
    result: bool = False

    # retrieve the scheduler
    scheduler: _ThreadedScheduler = __get_scheduler(errors, badge)

    # proceed, if the scheduler was retrieved
    if scheduler:
        scheduler.stop()
        result = True

    return result


def scheduler_add_job(errors: list[str] | None,
                      job: callable,
                      job_id: str,
                      job_name: str,
                      job_cron: str = None,
                      job_start: datetime = None,
                      job_args: tuple = None,
                      job_kwargs: dict = None,
                      badge: str = __DEFAULT_BADGE,
                      logger: Logger = None) -> bool:
    """
    Schedule the job identified as *job_id* and named as *job_name*.

    The scheduling is performed with the *CRON* expression *job_cron*, starting at the timestamp *job_start*.
    Positional arguments for the scheduled job may be provided in *job_args*.
    Named arguments for the scheduled job may be provided in *job_kwargs*.
    Return *True* if the scheduling was successful.

    :param errors: incidental errors
    :param job: the job to be scheduled
    :param job_id: the id of the job to be scheduled
    :param job_name: the name of the job to be scheduled
    :param job_cron: the CRON expression
    :param job_start: the start timestamp
    :param job_args: the positional arguments for the scheduled job
    :param job_kwargs: the named arguments for the scheduled job
    :param badge: badge identifying the scheduler (defaults to __DEFAULT_BADGE)
    :param logger: optional logger
    :return: True if the job was successfully scheduled, or False otherwise
    """
    # initialize the return variable
    result: bool = False

    # retrieve the scheduler
    scheduler: _ThreadedScheduler = __get_scheduler(errors=errors,
                                                    badge=badge)

    # was the scheduler retrieved ?
    if scheduler:
        # yes, proceed
        result = __scheduler_add_job(errors=errors,
                                     scheduler=scheduler,
                                     job=job,
                                     job_id=job_id,
                                     job_name=job_name,
                                     job_cron=job_cron,
                                     job_start=job_start,
                                     job_args=job_args,
                                     job_kwargs=job_kwargs,
                                     logger=logger)
    return result


def scheduler_add_jobs(errors: list[str] | None,
                       jobs: list[tuple[callable, str, str, str, datetime, tuple, dict]],
                       badge: str = __DEFAULT_BADGE,
                       logger: Logger = None) -> int:
    r"""
    Schedule the jobs described in *jobs*, starting at the given timestamp.

    Each element in the job list is a *tuple* with the following job data items:
        - callable function: the function to be invoked by the scheduler (*callable*)
        - job id: the id of the job to be started (*str*)
        - job name: the name of the job to be started (*str*)
        - start timestamp: the date and time to start scheduling the job (*datetime*)
        - job args: the positional arguments (*\*args*) to be passed to the job (*tuple*)
        - job kwargs: the named arguments (*\*\*kwargs*) to be passed to the job (*dict*)
    Only the first three data items are required.

    :param errors: incidental errors
    :param jobs: list of tuples describing the jobs to be scheduled
    :param badge: badge identifying the scheduler (defaults to __DEFAULT_BADGE)
    :param logger: optional logger
    :return: the number of jobs effectively scheduled
    """
    # initialize the return variable
    result: int = 0

    # retrieve the scheduler
    scheduler: _ThreadedScheduler = __get_scheduler(errors=errors,
                                                    badge=badge)

    # proceed, if the scheduler was retrieved
    if scheduler:
        # traverse the job list and attempt the scheduling
        for job in jobs:
            # process the required parameters
            job_function: callable = job[0]
            job_id: str = job[1]
            job_name: str = job[2]

            # process the optional arguments
            job_cron: str = job[3] if len(job) > 3 else None
            job_start: datetime = job[4] if len(job) > 4 else None
            job_args: tuple = job[5] if len(job) > 5 else None
            job_kwargs: dict = job[6] if len(job) > 6 else None
            # add to the return valiable, if scheduling was successful
            if __scheduler_add_job(errors=errors,
                                   scheduler=scheduler,
                                   job=job_function,
                                   job_id=job_id,
                                   job_name=job_name,
                                   job_cron=job_cron,
                                   job_start=job_start,
                                   job_args=job_args,
                                   job_kwargs=job_kwargs,
                                   logger=logger):
                result += 1

    return result


def __get_scheduler(errors: list[str] | None,
                    badge: str,
                    must_exist: bool = True,
                    logger: Logger = None) -> _ThreadedScheduler:
    """
    Retrieve the scheduler identified by *badge*.

    :param errors: incidental errors
    :param badge: badge identifying the scheduler
    :param must_exist: True if scheduler must exist
    :param logger: optional logger
    :return: the scheduler retrieved, or None otherwise
    """
    result: _ThreadedScheduler = __schedulers.get(badge)
    if must_exist and result is None:
        err_msg: str = f"Job scheduler '{badge}' has not been created"
        if logger:
            logger.error(msg=err_msg)
        if isinstance(errors, list):
            errors.append(err_msg)

    return result


def __scheduler_add_job(errors: list[str],
                        scheduler: _ThreadedScheduler,
                        job: callable,
                        job_id: str,
                        job_name: str,
                        job_cron: str = None,
                        job_start: datetime = None,
                        job_args: tuple = None,
                        job_kwargs: dict = None,
                        logger: Logger = None) -> bool:
    r"""
    Use *scheduler* to schedule the job identified as *job_id* and named as *job_name*.

    The scheduling is performed with the *CRON* expression *job_cron*, starting at the timestamp *job_start*.
    Positional arguments for the scheduled job may be provided in *job_args*.
    Named arguments for the scheduled job may be provided in *job_kwargs*.
    Return *True* if the scheduling was successful.

    :param errors: incidental errors
    :param scheduler: the scheduler to use
    :param job: the job to be scheduled
    :param job_id: the id of the job to be scheduled
    :param job_name: the name of the job to be scheduled
    :param job_cron: the CRON expression
    :param job_start: the date and time to start scheduling the the job
    :param job_args: the positional arguments (*\*args*) to be passed to the job
    :param job_kwargs: the named arguments (*\*\*kwargs*) to be passed to the job
    :param logger: optional logger
    :return: True if the job was successfully scheduled, or False otherwise
    """
    # initialize the return variable
    result: bool = False

    err_msg: str | None = None
    # has a valid CRON expression been provided ?
    if job_cron and not re.search(pattern=__REGEX_VERIFY_CRON,
                                  string=job_cron):
        # no, report the error
        err_msg = f"Invalid CRON expression: '{job_cron}'"
    else:
        # yes, proceed with the scheduling
        try:
            scheduler.schedule_job(job=job,
                                   job_id=job_id,
                                   job_name=job_name,
                                   job_cron=job_cron,
                                   job_start=job_start,
                                   job_args=job_args,
                                   job_kwargs=job_kwargs)
            result = True
        except Exception as e:
            err_msg = (
                f"Error scheduling the job '{job_name}', id '{job_id}', "
                f"with CRON '{job_cron}': {exc_format(e, sys.exc_info())}"
            )
    if err_msg:
        if logger:
            logger.error(msg=err_msg)
        if isinstance(errors, list):
            errors.append(err_msg)

    return result
