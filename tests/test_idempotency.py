import pytest

from app.services.idempotency import claim_idempotency_key


@pytest.mark.asyncio
async def test_idempotency_key_can_only_be_claimed_once() -> None:
    namespace = "pytest-flow"
    key = "same-event"

    first = await claim_idempotency_key(namespace, key, ttl_seconds=60)
    second = await claim_idempotency_key(namespace, key, ttl_seconds=60)

    assert first is True
    assert second is False
