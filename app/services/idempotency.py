from redis.asyncio import Redis

from app.core.config import settings


async def claim_idempotency_key(namespace: str, key: str, ttl_seconds: int = 3600) -> bool:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        claimed = await redis.set(f"idem:{namespace}:{key}", "1", ex=ttl_seconds, nx=True)
        return bool(claimed)
    finally:
        await redis.aclose()
