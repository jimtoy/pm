import os
from contextlib import asynccontextmanager, closing
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.ai import router as ai_router
from app.auth import router as auth_router
from app.board import router as board_router
from app.chat import router as chat_router
from app.db import connect, init_db

load_dotenv()

DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR = Path(os.environ.get("STATIC_DIR", DEFAULT_STATIC_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    with closing(connect()) as conn:
        init_db(conn)
    yield


app = FastAPI(title="Project Management MVP", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-only-insecure-secret"),
    same_site="lax",
)

app.include_router(auth_router)
app.include_router(board_router)
app.include_router(ai_router)
app.include_router(chat_router)


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from FastAPI"}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
