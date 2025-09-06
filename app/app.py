from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .settings import settings
from .db import wait_for_postgres, ensure_schema_and_seed, load_entities
from .cache import wait_for_redis, register_decr_lua
from .api import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("terac-routing")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Connecting to Redis...")
    r = wait_for_redis(settings.REDIS_URL)
    logger.info("Connecting to Postgres...")
    engine = wait_for_postgres(settings.SUPABASE_DB_URL)

    ensure_schema_and_seed(engine, settings.USERS_PATH, settings.INTERVIEWERS_PATH, logger)
    users, interviewers = load_entities(engine)

    for itv in interviewers:
        r.setnx(f"interviewer:{itv['interviewer_id']}:queue", 0)

    decr_lua = register_decr_lua(r)

    app.state.redis = r
    app.state.engine = engine
    app.state.users = users
    app.state.interviewers = interviewers
    app.state.decr_lua = decr_lua

    logger.info("Startup complete. users=%d interviewers=%d", len(users), len(interviewers))
    try:
        yield
    finally:
        try:
            engine.dispose()
        except Exception:
            pass
        try:
            r.close()
        except Exception:
            pass
        logger.info("Shutdown complete.")

app = FastAPI(
    title="Terac Routing Demo (Supabase + Redis, capacity-guarded)",
    lifespan=lifespan,
)
app.include_router(api_router)
