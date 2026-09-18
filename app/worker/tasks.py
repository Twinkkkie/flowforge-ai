import asyncio
from uuid import UUID

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.execution import execute_workflow_run


async def _run(execution_id: str) -> None:
    async with SessionLocal() as db:
        await execute_workflow_run(db, UUID(execution_id))


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def run_execution(self, execution_id: str) -> None:
    asyncio.run(_run(execution_id))
