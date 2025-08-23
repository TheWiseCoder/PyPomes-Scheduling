import threading
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from logging import Logger
from zoneinfo import ZoneInfo


class _ThreadedScheduler(threading.Thread):
    """
    A scalable implementation of *APScheduler*'s *BlockingScheduler*.

    This implementation may run as single or multiple instances, each instance on its own thread.
    """

    def __init__(self,
                 timezone: ZoneInfo,
                 retry_interval: int,
                 logger: Logger = None) -> None:
        """
        Initialize the scheduler.

        This is the simplest possible scheduler. It runs on the foreground of its own thread, so when
        *start()* is invoked, the call never returns.

        :param timezone: the reference timezone in job timestamps
        :param retry_interval: interval between retry attempts, in minutes
        :param logger: optional logger to use for logging the scheduler's operations
        """
        threading.Thread.__init__(self)

        # instance attributes
        self.stopped: bool = False
        self.logger: Logger = logger
        self.scheduler: BlockingScheduler = BlockingScheduler(logging=logger,
                                                              timezone=timezone,
                                                              jobstore_retry_interval=retry_interval)
        if self.logger:
            self.logger.debug(msg=(f"Instanced, with timezone '{timezone}' "
                                   f"and retry interval '{retry_interval}'"))

    def run(self) -> None:
        """
        Start the scheduler in its own thread.
        """
        # stay in loop until 'stop()' is invoked
        while not self.stopped:
            if self.logger:
                self.logger.debug("Started")

            # start the scheduler, blocking the thread until it is interrupted
            self.scheduler.start()

        self.scheduler.shutdown()
        if self.logger:
            self.logger.debug("Finished")

    def stop(self) -> None:
        """
        Stop the scheduler.
        """
        if self.logger:
            self.logger.debug("Stopping...")
        self.stopped = True

    def schedule_job(self,
                     job: callable,
                     job_id: str,
                     job_name: str,
                     job_cron: str = None,
                     job_start: datetime = None,
                     job_args: tuple = None,
                     job_kwargs: dict = None) -> None:
        """
        Schedule the given *job*, with the given parameters.

        A valid *CRON* expression has the syntax *<min> <hour> <day> <month> <day-of-week>*, and can include:
          - numbers (e.g. '5')
          - ranges (e.g. '1-5')
          - lists (e.g. '1,2,3')
          - steps (e.g. '*/15')
          - wildcards ('*')

        :param job: the callable object to be scheduled
        :param job_id: the id of the scheduled job
        :param job_name: the name of the scheduled job
        :param job_cron: the CRON expression directing the execution times
        :param job_start: the start timestamp for the scheduling process
        :param job_args: the '*args' arguments to be passed to the scheduled job
        :param job_kwargs: the '**kwargs' arguments to be passed to the scheduled job
        """
        aps_trigger: CronTrigger | None = None
        # has the CRON expression been defined ?
        if job_cron:
            # yes, build the trigger
            vals: list[str] = job_cron.split()
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
        if self.logger:
            self.logger.debug(msg=f"Job '{job_name}' scheduled, with CRON '{job_cron}'")
