import logging
import pytz
import threading
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger


class _ThreadedScheduler(threading.Thread):
    """
    A scalable implementation of *APScheduler*'s *BlockingScheduler*.

    This implementation may run as single or multiple instances, each instance on its own thread.
    """
    # instance attributes
    scheduler: BlockingScheduler
    logger: logging.Logger
    stopped: bool

    def __init__(self, timezone: pytz.timezone, retry_interval: int, logger: logging.Logger = None) -> None:
        """
        Initialize the scheduler.

        This is the simplest possible scheduler. It runs on the foreground of its own thread, so when
        *start()* is invoked, the call never returns.

        :param timezone: the reference timezone in job timestamps
        :param retry_interval: interval between retry attempts, in minutes
        :param logger: optional logger to use for logging the scheduler's operations
        """
        threading.Thread.__init__(self)

        self.stopped = False
        self.logger = logger
        self.scheduler = BlockingScheduler(logging=logger,
                                           timezone=timezone,
                                           jobstore_retry_interval=retry_interval)
        if self.logger is not None:
            self.logger.info("Instanced, with timezone "
                             f"'{timezone}' and retry interval '{retry_interval}'")

    def run(self) -> None:
        """
        Start the scheduler in its own thread.
        """
        # stay in loop until 'stop()' is invoked
        while not self.stopped:
            if self.logger is not None:
                self.logger.info("Started")

            # start the scheduler, blocking the thread until it is interrupted
            self.scheduler.start()

        self.scheduler.shutdown()
        if self.logger is not None:
            self.logger.info("Finished")

    def stop(self) -> None:
        """
          Stop the scheduler.
        """
        if self.logger is not None:
            self.logger.info("Stopping...")
        self.stopped = True

    def schedule_job(self, job: callable, job_id: str, job_name: str, job_cron: str = None,
                     job_start: datetime = None, job_args: tuple = None, job_kwargs: dict = None) -> None:
        """
        Schedule the given *job*, with the given parameters.

        :param job: the callable object to be scheduled
        :param job_id: the id of the scheduled job
        :param job_name: the name of the scheduled job
        :param job_cron: the CRON expression directing the execution times
        :param job_start: the start timestamp for the scheduling process
        :param job_args: the '*args' arguments to be passed to the scheduled job
        :param job_kwargs: the '**kwargs' arguments to be passed to the scheduled job
        """
        # approximately, convert symbols to CRON expression
        cron_expr: str | None
        match job_cron:
            case "@reboot":
                cron_expr = "1 0 * * *"                      # daily, at 00h01
            case "@midnight":
                cron_expr = "0 0 * * *"                      # daily, at 00h00
            case "@hourly":
                cron_expr = "0 * * * *"                      # every hour, at minute 0 (??h00)
            case "@daily":
                cron_expr = "1 0 * * *"                      # daily, at 00h01
            case "@weekly":
                cron_expr = "0 0 * * 0"                      # on sundays, at 00h00
            case "@monthly":
                cron_expr = "0 0 1 * *"                      # on the first day of the month, at 00h00
            case "@yearly" | "@annually":
                cron_expr = "0 0 1 1 *"                      # on January 1st, at 00h00
            case None:
                cron_expr = None
            case _:
                cron_expr = job_cron

        aps_trigger: CronTrigger | None = None
        # has the CRON expression been defined ?
        if cron_expr is not None:
            # yes, build the trigger: <minute> <hour> <day-of-month> <month> <day-of-week>
            vals: list[str] = cron_expr.split()
            vals = [None if val == "?" else val for val in vals]
            aps_trigger = CronTrigger(minute=vals[0],
                                      hour=vals[1],
                                      day=vals[2],
                                      month=vals[3],
                                      day_of_week=vals[4],
                                      start_date=job_start)
        self.scheduler.add_job(func=job,
                               trigger=aps_trigger,
                               args=job_args,
                               kwargs=job_kwargs,
                               id=job_id,
                               name=job_name)
        if self.logger is not None:
            self.logger.info(f"Job '{job_name}' scheduled, with CRON '{job_cron}'")
