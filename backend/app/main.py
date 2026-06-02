import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.athena import router as athena_router
from app.api.catalog import router as catalog_router
from app.api.chat import router as chat_router
from app.api.datasets import router as datasets_router
from app.api.glossary import router as glossary_router
from app.api.routines import router as routines_router
from app.api.saved_queries import router as saved_queries_router
from app.api.threads import router as threads_router
from app.core.config import settings
from app.core.db import create_all_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all_tables()

    from app.agents.schema_agent import init_chroma
    init_chroma()

    from app.agents.graph import build_graph, make_postgres_checkpointer

    _pool = None
    if settings.POSTGRES_URL:
        try:
            _pool, checkpointer = await make_postgres_checkpointer(settings.POSTGRES_URL)
            logger.info("[startup] PostgreSQL checkpointer ready — HITL state is persistent across restarts")
        except Exception as exc:
            logger.warning(
                "[startup] PostgreSQL checkpointer failed (%s) — falling back to MemorySaver. "
                "HITL approval state WILL BE LOST on server restart. Set POSTGRES_URL to fix this.",
                exc,
            )
            from langgraph.checkpoint.memory import MemorySaver
            checkpointer = MemorySaver()
    else:
        logger.warning(
            "[startup] POSTGRES_URL not configured — using in-memory MemorySaver. "
            "HITL approval state WILL BE LOST on server restart. Set POSTGRES_URL in .env to fix this."
        )
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()

    app.state.graph = build_graph(checkpointer)

    yield

    if _pool is not None:
        await _pool.close()


app = FastAPI(title="Business Assistant API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(datasets_router, prefix="/api")
app.include_router(glossary_router, prefix="/api")
app.include_router(threads_router, prefix="/api")
app.include_router(catalog_router, prefix="/api")
app.include_router(athena_router, prefix="/api")
app.include_router(saved_queries_router, prefix="/api")
app.include_router(routines_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
