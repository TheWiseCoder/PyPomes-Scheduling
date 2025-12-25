import threading
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from collections.abc import Callable
from datetime import datetime
from logging import Logger
from zoneinfo import ZoneInfo


class _ThreadedScheduler(threading.Thread):
    """
    A scalable implementation of *APScheduler*'s *BlockingScheduler*.

    This implementation may run as single or multiple instances, each instance on its own thread.
    """
    # the class logger
    LOGGER: Logger | None = None

    def __init__(self,
                 timezone: ZoneInfo,
                 retry_interval: int) -> None:
        """
        Initialize the scheduler.

        This is the simplest possible scheduler. It runs on the foreground of its own thread, so when
        *start()* is invoked, the call never returns.

        :param timezone: the reference timezone in job timestamps
        :param retry_interval: interval between retry attempts, in minutes
        """
        threading.Thread.__init__(self)

        # instance attributes
        self.stopped: bool = False
        self.scheduler: BlockingScheduler = BlockingScheduler(logging=_ThreadedScheduler.LOGGER,
                                                              timezone=timezone,
                                                              jobstore_retry_interval=retry_interval)
        if _ThreadedScheduler.LOGGER:
            _ThreadedScheduler.LOGGER.debug(msg=f"Instanced, with timezone '{timezone}' "
                                                f"and retry interval '{retry_interval}'")

    def run(self) -> None:
        """
        Start the scheduler in its own thread.
        """
        # stay in loop until 'stop()' is invoked
        while not self.stopped:
            if _ThreadedScheduler.LOGGER:
                _ThreadedScheduler.LOGGER.debug("Started")

            # start the scheduler, blocking the thread until it is interrupted
            self.scheduler.start()

        self.scheduler.shutdown()
        if _ThreadedScheduler.LOGGER:
            _ThreadedScheduler.LOGGER.debug("Finished")

    def stop(self) -> None:
        """
        Stop the scheduler.
        """
        if _ThreadedScheduler.LOGGER:
            _ThreadedScheduler.LOGGER.debug("Stopping...")
        self.stopped = True

    def schedule_job(self,
                     job: Callable,
                     job_id: str,
                     job_name: str,
                     job_cron: str = None,
                     job_start: datetime = None,
                     job_args: tuple = None,
                     job_kwargs: dict = None) -> None:
        """
        Schedule the given *job*, with the given parameters.

        A valid *CRON* expression has the syntax *[<sec>] <min> <hour> <day> <month> <day-of-week> [<year>]*,
        where *sec* and <year> are optional, and can include:
          - numbers (e.g. '5')
          - ranges (e.g. '1-5')
          - lists (e.g. '1,2,3')
          - steps (e.g. '*/15')
          - mnemonics (e.g. 'JAN', 'SUN')
          - wildcards ('*')

        :param job: the Callable object to be scheduled
        :param job_id: the id of the scheduled job
        :param job_name: the name of the scheduled job
        :param job_cron: the CRON expression directing the execution times
        :param job_start: the start timestamp for the scheduling process
        :param job_args: the '*args' arguments to be passed to the scheduled job
        :param job_kwargs: the '**kwargs' arguments to be passed to the scheduled job
        """
        aps_trigger: CronTrigger | None = None
        if job_cron:
            # CRON expression has been defined, build the trigger
            vals: list[str] = job_cron.split()
            vals = [None if val == "?" else val for val in vals]
            year: str = vals[6] if len(vals) == 7 else None
            aps_trigger = CronTrigger(second=vals[0],
                                      minute=vals[1],
                                      hour=vals[2],
                                      day=vals[3],
                                      month=vals[4],
                                      year=year,
                                      day_of_week=vals[5],
                                      start_date=job_start)
        self.scheduler.add_job(func=job,
                               trigger=aps_trigger,
                               args=job_args,
                               kwargs=job_kwargs,
                               id=job_id,
                               name=job_name)
        if _ThreadedScheduler.LOGGER:
            _ThreadedScheduler.LOGGER.debug(msg=f"Job '{job_name}' scheduled, with CRON '{job_cron}'")

    @staticmethod
    def set_logger(logger: Logger) -> None:
        """
        Establish the class logger.

        :param logger: the class logger
        """
        _ThreadedScheduler.LOGGER = logger
