from datetime import datetime
from pypomes_core import exc_format
from typing import Final
import logging
import pytz
import re
import sys
from .__threaded_scheduler import __ThreadedScheduler

__DEFAULT_BADGE: Final[str] = "__default__"

__REGEX_VERIFY_CRON: Final[str] = "/(@(annually|yearly|monthly|weekly|daily|hourly|reboot))|" \
                                  "(@every (\d+(ns|us|µs|ms|s|m|h))+)|((((\d+,)+\d+|(\d+(\/|-)\d+)|\d+|\*) ?){5,7})"

__schedulers: dict = {}


def scheduler_create(errors: list[str], timezone: pytz.BaseTzInfo,
                     retry_interval: int, logger: logging.Logger = None, badge: str = None) -> bool:
    """
    Create the threaded job scheduler. This is a wrapper around the package *APScheduler*.

    :param errors: incidental errors
    :param timezone: the timezone to be used
    :param retry_interval: interval between retry attempts, in minutes
    :param logger: optional logger object
    :param badge: optional badge identifying the scheduler
    :return: True if the scheduler was created, or False otherwise
    """
    # inicialize the return variable
    result: bool = False
    
    # define the badge
    curr_badge: str = badge or __DEFAULT_BADGE
    
    # has the scheduler been created ?
    if __get_scheduler(errors, curr_badge, False) is None:
        # no, create it
        try:
            __schedulers[curr_badge] = __ThreadedScheduler(timezone, retry_interval, logger)
            __schedulers[curr_badge].daemon = True
            result = True
        except Exception as e:
            errors.append(f"Error creating the job scheduler '{curr_badge}': "
                          f"{exc_format(e, sys.exc_info())}")

    return result


def scheduler_add_job(errors: list[str], job: callable, job_id: str, job_name: str,
                      job_cron: str = None, job_start: datetime = None,
                      job_args: tuple = None, job_kwargs: dict = None, badge: str = None) -> bool:
    """
    Schedule the job identified as *job_id* and named as *job_name*,
    with the *CRON* expression *job_cron*, starting at the timestamp *job_start*.
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
    :param badge: optional badge identifying the scheduler
    :return: True if the job was successfully scheduled, or False otherwise
    """
    # initialize the return variable
    result: bool = False
    
    # retrieve the scheduler
    scheduler: __ThreadedScheduler = __get_scheduler(errors, badge)
    
    # proceed, if the scheduler was retrieved
    if scheduler is not None:
        # has a valid CRON expression been provided ?
        if job_cron is not None and re.search(__REGEX_VERIFY_CRON, job_cron) is None:
            # no, report the error
            errors.append(f"Invalid CRON expression: '{job_cron}'")
        else:
            # yes, proceed with the scheduling
            try:
                scheduler.schedule_job(job, job_id, job_name, job_cron, job_start, job_args, job_kwargs)
                result = True
            except Exception as e:
                errors.append(f"Error scheduling the job '{job_name}', id '{job_id}', "
                              f"with CRON '{job_cron}': {exc_format(e, sys.exc_info())}")

    return result


def scheduler_add_jobs(errors: list[str],
                       jobs: list[tuple[callable, str, str, str, datetime, tuple, dict]],
                       badge: str = None) -> int:
    """
    Schedule the jobs described in *jobs*, starting at the given *start*.
    Each element in the job list is a *tuple* with the corresponding job data:
    *(callable function, job id, job name, CRON expression, start timestamp, job args, job kwargs)*.
    Only the first three data items are required.

    :param errors: incidental errors
    :param jobs: list of tuples containing the jobs to schedule
    :param badge: optional badge identifying the scheduler
    :return: the number of jobs effectively scheduled
    """
    # initialize the return variable
    result: int = 0
    
    # retrieve the scheduler
    scheduler: __ThreadedScheduler = __get_scheduler(errors, badge)
    
    # proceed, if the scheduler was retrieved
    if scheduler is not None:
        # traverse the job list and attempt the scheduling
        for job in jobs:
            # process the optional arguments
            job_cron: str = job[3] if len(job) > 3 else None
            job_start: datetime = job[4] if len(job) > 4 else None
            job_args: tuple = job[5] if len(job) > 5 else None
            job_kwargs: dict = job[6] if len(job) > 6 else None
            # add to the return valiable, if scheduling was successful
            if scheduler_add_job(errors, job[0], job[1], job[2],
                                 job_cron, job_start, job_args, job_kwargs, badge):
                result += 1

    return result


def scheduler_start(errors: list[str], badge: str = None):
    """
    Start the scheduler.

    :param errors: incidental errors
    :param badge: optional badge identifying the scheduler
    :return: True if the scheduler has been started, False otherwise
    """
    # initialize the return variable
    result: bool = False
    
    # retrieve the scheduler
    scheduler: __ThreadedScheduler = __get_scheduler(errors, badge)
    
    # proceed, if the scheduler was retrieved
    if scheduler is not None:
        try:
            scheduler.start()
            result = True
        except Exception as e:
            errors.append(f"Error starting the scheduler '{badge or __DEFAULT_BADGE}': "
                          f"{exc_format(e, sys.exc_info())}")

    return result


def scheduler_stop(errors: list[str], badge: str = None):
    """
    Stop the scheduler.

    :param errors: incidental errors
    :param badge: optional badge identifying the scheduler
    :return: True if the scheduler has been stopped, False otherwise
    """
    # initialize the return variable
    result: bool = False

    # retrieve the scheduler
    scheduler: __ThreadedScheduler = __get_scheduler(errors, badge)

    # proceed, if the scheduler was retrieved
    if scheduler is not None:
        scheduler.stop()
        result = True

    return result


def __get_scheduler(errors: list[str], badge: str, must_exist: bool = True) -> __ThreadedScheduler:
    """
    Retrieve the scheduler identified by *badge*.

    :param errors: incidental errors
    :param badge: optional badge identifying the scheduler
    :param must_exist: True if scheduler must exist
    :return: the scheduler retrieved, or None otherwise
    """
    
    curr_badge = badge or __DEFAULT_BADGE
    result: __ThreadedScheduler = __schedulers[curr_badge]
    if must_exist and result is None:
        errors.append(f"Job scheduler '{curr_badge}' has not been created")
    elif not must_exist and result is not None:
        errors.append(f"Job scheduler '{curr_badge}' has already been created")
        
    return result
