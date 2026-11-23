from __future__ import annotations

import asyncio
import contextlib
import logging
import os

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import DatabaseError, close_pool, ping_database
from app.routers import staffing
from app.rv.routes import router as resource_vision_router
from app.runtime import azure_sql_configured, runtime_info

logger = logging.getLogger("staffing")


def _warm_up() -> None:
    """Load availability and skills before the first user request needs them."""
    from app.ports import get_ports
    from app.rv import service as rv_service

    rv_service.warm_up()
    try:
        get_ports(get_settings().dev_launch_token).skills.get_options()
    except Exception:  # noqa: BLE001
        logger.exception("Skills warm-up failed; it will load on first request")


async def _outbox_loop(interval: int) -> None:
    """Publish queued events (debounced) so availability caches pick up reservations."""
    from app.ports import get_ports
    from app.staffing_store import get_staffing_store
    from app.workers.outbox import publish_pending

    while True:
        await asyncio.sleep(max(1, interval))
        try:
            ports = get_ports(get_settings().dev_launch_token)
            await asyncio.to_thread(publish_pending, get_staffing_store(), ports)
        except Exception:  # noqa: BLE001 - keep the worker alive
            logger.exception("Outbox publish failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    mode = settings.resolved_rv_data_source()
    os.environ["RV_DATA_SOURCE"] = mode
    info = runtime_info()
    logger.info(
        "Data mode: %s (rv_data_source=%s, staffing_persistence=%s, azure_sql_configured=%s)",
        info["data_mode"],
        info["rv_data_source"],
        info["staffing_persistence"],
        info["azure_sql_configured"],
    )
    if mode != "demo" and not azure_sql_configured():
        logger.warning(
            "RV_DATA_MODE/RV_DATA_SOURCE is %s but Azure SQL credentials are missing. "
            "Set AZURE_SQL_* in .env or use RV_DATA_MODE=demo.",
            mode,
        )
    asyncio.get_running_loop().run_in_executor(None, _warm_up)
    task = asyncio.create_task(_outbox_loop(settings.outbox_poll_seconds))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        close_pool()


app = FastAPI(
    title="Resource Vision Confirmed Staffing API",
    description="Staffing orchestration plus read-only availability (rv2_* on Azure SQL).",
    version="0.2.0",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resource_vision_router)
app.include_router(staffing.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "staffing-api"}


@app.get("/api/database/status")
def database_status() -> dict[str, object]:
    try:
        info = ping_database()
    except DatabaseError as error:
        logging.getLogger("staffing").error("Database status check failed: %s", error)
        raise HTTPException(status_code=503, detail="The database is currently unavailable.") from error
    return {"connected": True, **info}