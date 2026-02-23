"""Lakebase MCP UI — FastAPI backend serving React SPA + metadata API."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from ui.backend.routers.metadata import router as metadata_router

app = FastAPI(title="Lakebase MCP UI", version="1.0.0")
app.include_router(metadata_router, prefix="/api")

STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=STATIC_DIR / "assets"),
        name="assets",
    )

    @app.get("/favicon.ico")
    async def favicon():
        ico = STATIC_DIR / "favicon.ico"
        if ico.exists():
            return FileResponse(ico)
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
