import pytest

from benchmark.utils.retry import async_retry


async def test_succeeds_on_first_attempt():
    calls = []

    @async_retry(max_attempts=3, backoff_factor=0)
    async def fn():
        calls.append(1)
        return "ok"

    result = await fn()
    assert result == "ok"
    assert len(calls) == 1


async def test_retries_and_succeeds():
    calls = []

    @async_retry(max_attempts=3, backoff_factor=0)
    async def fn():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("falha temporária")
        return "ok"

    result = await fn()
    assert result == "ok"
    assert len(calls) == 3


async def test_raises_after_max_attempts():
    calls = []

    @async_retry(max_attempts=3, backoff_factor=0)
    async def fn():
        calls.append(1)
        raise RuntimeError("erro persistente")

    with pytest.raises(RuntimeError, match="erro persistente"):
        await fn()

    assert len(calls) == 3


async def test_single_attempt_raises_immediately():
    @async_retry(max_attempts=1, backoff_factor=0)
    async def fn():
        raise ValueError("erro")

    with pytest.raises(ValueError):
        await fn()


async def test_non_retryable_error_is_not_retried():
    from benchmark.utils.retry import NonRetryableError

    calls = []

    @async_retry(max_attempts=3, backoff_factor=0)
    async def fn():
        calls.append(1)
        raise NonRetryableError("bloqueado")

    with pytest.raises(NonRetryableError):
        await fn()
    assert len(calls) == 1
