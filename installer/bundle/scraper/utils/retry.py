"""Async retry with exponential backoff."""

import asyncio
import functools
import logging
from typing import Any, Callable, TypeVar, ParamSpec

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Callable[[Exception, int], None] | None = None,
):
    """
    Decorator for async functions with exponential backoff retry.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay cap
        backoff_factor: Multiplier for each subsequent delay
        exceptions: Tuple of exception types to catch
        on_retry: Optional callback(exception, attempt_number) called before each retry
    """

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            last_exception: Exception | None = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise
                    
                    delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
                    # Add jitter (±25%)
                    import random
                    jitter = delay * 0.25 * (2 * random.random() - 1)
                    delay = max(0.1, delay + jitter)
                    
                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    if on_retry:
                        on_retry(e, attempt)
                    
                    await asyncio.sleep(delay)
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


async def retry_async(
    coro_factory: Callable[[], Any],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Any:
    """
    Functional retry for one-off async calls.
    
    Args:
        coro_factory: Callable that returns a coroutine to retry
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries
        max_delay: Maximum delay cap
        backoff_factor: Multiplier for delay
        exceptions: Tuple of exception types to catch
    
    Returns:
        Result of the coroutine
    """
    import random
    
    last_exception: Exception | None = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            return await coro_factory()
        except exceptions as e:
            last_exception = e
            if attempt == max_attempts:
                raise
            delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
            jitter = delay * 0.25 * (2 * random.random() - 1)
            delay = max(0.1, delay + jitter)
            await asyncio.sleep(delay)
    
    if last_exception:
        raise last_exception
