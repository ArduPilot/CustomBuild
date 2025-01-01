import logging
import threading
import time

logger = logging.getLogger(__name__)


class TaskRunner:
    """
    Class to run a list of tasks periodically at a given interval.
    """
    def __init__(self, tasks: tuple[tuple]) -> None:
        """
        Initialize the TaskRunner.

        Parameters:
            tasks (tuple): Tuple of tuples containing the callable
                           and the calling period in seconds.
        """
        self.__tasks = tasks
        self.__stop_event = threading.Event()
        self.__thread = threading.Thread(target=self.__run, daemon=True)

    def start(self) -> None:
        """
        Start executing the tasks.
        """
        logger.info("Started a task runner thread.")
        logger.info(f"Tasks: {str(self.__tasks)}")
        self.__thread.start()

    def __run(self) -> None:
        """
        Private method where the thread executes the given methods
        at their specified frequencies.
        """
        next_call_times = [time.time() for _ in self.__tasks]

        while not self.__stop_event.is_set():
            now = time.time()

            for i, task in enumerate(self.__tasks):
                to_call, period = task
                if now >= next_call_times[i]:
                    logger.debug(
                        f"Now: {now}, Calling: {str(to_call)}, "
                        f"Runner id: {id(self)}"
                    )
                    to_call()  # Call the method
                    next_call_times[i] = now + period

            # Wait for the next call or stop event
            earliest_next_call_time = min(next_call_times) - now
            logger.debug(
                f"Time to next call: {earliest_next_call_time} sec, "
                f"Runner id: {id(self)}"
            )
            if earliest_next_call_time > 0:
                self.__stop_event.wait(earliest_next_call_time)

    def __del__(self) -> None:
        """
        Cleanup resources when the object is destroyed.
        """
        self.stop()

    def stop(self) -> None:
        """
        Signal the thread to stop and wait for graceful exit.
        """
        logger.debug(f"Firing stop event, Runner id: {id(self)}")
        self.__stop_event.set()
        if self.__thread.is_alive():
            logger.debug(
                f"Waiting for the runner thread to terminate, "
                f"Runner id: {id(self)}"
            )
            self.__thread.join()
