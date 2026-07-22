import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

DEFAULT_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR = Path(os.environ.get("STATIC_DIR", DEFAULT_STATIC_DIR))

app = FastAPI(title="Project Management MVP")


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from FastAPI"}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
