"""
utils/retry.py
──────────────
Reusable retry decorators built on top of `tenacity`.

Provides two decorators:
  • @with_retry       — for synchronous functions
  • @with_async_retry — for async / coroutine functions

Both implement exponential back-off with jitter so that thundering-herd
problems don't emerge when many API calls fail simultaneously.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Tuple, Type, TypeVar

from tenacity import (
    AsyncRetrying,
    RetryError,
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Exceptions that should never be retried (programming errors)
_NEVER_RETRY: Tuple[Type[Exception], ...] = (
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
)


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    reraise: bool = True,
) -> Callable[[F], F]:
    """
    Decorator — retry a *synchronous* function with exponential back-off.

    Parameters
    ----------
    max_attempts: Maximum total call attempts (including the first).
    min_wait:     Minimum seconds between retries.
    max_wait:     Maximum seconds between retries.
    reraise:      If True, re-raise the last exception after all attempts fail.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            retryer = Retrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential_jitter(initial=min_wait, max=max_wait),
                retry=retry_if_not_exception_type(_NEVER_RETRY),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=reraise,
            )
            try:
                return retryer(func, *args, **kwargs)
            except RetryError as exc:
                logger.error(
                    "All %d attempts failed for %s: %s",
                    max_attempts,
                    func.__qualname__,
                    exc.last_attempt.exception(),
                )
                if reraise:
                    raise exc.last_attempt.exception()  # type: ignore[misc]
                return None

        return wrapper  # type: ignore[return-value]

    return decorator


def with_async_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    reraise: bool = True,
) -> Callable[[F], F]:
    """
    Decorator — retry an *async* function with exponential back-off.

    Parameters match ``with_retry``.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential_jitter(initial=min_wait, max=max_wait),
                retry=retry_if_not_exception_type(_NEVER_RETRY),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=reraise,
            ):
                with attempt:
                    return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
