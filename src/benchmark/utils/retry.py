import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger("benchmark")

T = TypeVar("T")


class NonRetryableError(Exception):
    """Erro determinístico: repetir a chamada não muda o resultado."""


def async_retry(max_attempts: int, backoff_factor: float) -> Callable:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except NonRetryableError:
                    raise
                except Exception as e:
                    if attempt == max_attempts:
                        raise
                    wait = backoff_factor ** (attempt - 1)
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {wait:.1f}s..."
                    )
                    await asyncio.sleep(wait)

        return wrapper

    return decorator
