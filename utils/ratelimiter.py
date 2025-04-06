import redis
import logging


class RateLimiter:
    """
    A rate limiter that uses Redis as a backend to store request counts.

    This class allows you to limit the number of requests made by a client
    (identified by a key) within a specified time window.
    """
    def __init__(self, redis_host: str, redis_port: int,
                 time_window_sec: int, allowed_requests: int) -> None:
        """
        Initialises the RateLimiter instance.

        Parameters:
            redis_host (str): The Redis server hostname.
            redis_port (int): The Redis server port.
            time_window_sec (int): The time window (in seconds) in which
            requests are counted.
            allowed_requests (int): The maximum number of requests allowed
            in the time window.
        """
        self.__redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(
            f"Redis connection established with {redis_host}:{redis_port}"
        )

        # Unique key prefix for this rate limiter instance
        self.__key_prefix = f"rl-{id(self)}-"
        self.__time_window_sec = time_window_sec
        self.__allowed_requests = allowed_requests

        self.logger.info(
            "RateLimiter initialized with parameters: "
            f"Key prefix: {self.__key_prefix}, "
            f"Time window: {self.__time_window_sec}s, "
            f"Allowed requests per window: {self.__allowed_requests}"
        )

    def __del__(self) -> None:
        """
        Clean up and close the Redis connection when the RateLimiter
        is deleted.
        """
        if self.__redis_client:
            self.__redis_client.close()
            self.logger.debug(
                f"Redis connection closed for RateLimiter with id {id(self)}"
            )

    def __get_prefixed_key(self, key: str) -> str:
        """
        Generates a unique key for Redis by adding a prefix.

        This helps avoid key collision in Redis with other data stored there.

        Parameters:
            key (str): The key (e.g., client identifier) to be used for rate
            limiting.

        Returns:
            str: The Redis key with the instance-specific prefix.
        """
        return self.__key_prefix + key

    def count(self, key: str) -> None:
        """
        Increment the request count for a specific key (e.g., an IP address)
        within the current time window.

        Parameters:
            key (str): The key for which the request count is being updated.
                      For example, an IP address if rate limiting based on IPs.

        Raises:
            RateLimitExceededException: If the number of requests exceeds the
            allowed limit for the current time window.
        """
        self.logger.debug(f"Counting a request for key: {key}")
        pfx_key = self.__get_prefixed_key(key)

        # Check if the key already exists in Redis
        if self.__redis_client.exists(pfx_key):
            current_count = int(self.__redis_client.get(pfx_key))
            self.logger.debug(
                f"Current request count for '{pfx_key}': {current_count}"
            )

            # If request count exceeds the allowed limit, raise exception
            if current_count >= self.__allowed_requests:
                self.logger.warning(f"Rate limit exceeded for key '{pfx_key}'")
                raise RateLimitExceededException

            # Increment request count and keep TTL (time-to-live) unchanged
            self.__redis_client.set(
                name=pfx_key,
                value=(current_count + 1),
                keepttl=True
            )
        else:
            # Key doesn't exist yet, initialise count with TTL for time window
            self.logger.debug(
                f"No previous requests for key '{pfx_key}' in current window"
                ", initialising count to 1"
            )
            self.__redis_client.set(
                name=pfx_key,
                value=1,
                ex=self.__time_window_sec
            )


class RateLimiterException(Exception):
    pass


class RateLimitExceededException(RateLimiterException):
    def __init__(self, *args):
        message = "Too many requests. Try after some time."
        super().__init__(message)
