from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.api.routes import ask as ask_routes
from backend.api.routes import nodes as nodes_routes
from backend.api.routes import admin as admin_routes
from backend.database.connection import engine

app = FastAPI(title="Astra API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(nodes_routes.router)
app.include_router(ask_routes.router)
app.include_router(admin_routes.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/db/ping")
async def db_ping() -> dict[str, str]:
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar_one()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unreachable: {exc}") from exc
    return {"db": "ok"}
