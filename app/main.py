"""
FastAPI 应用入口
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api.routes import router
from .core.config import settings

app = FastAPI(
    title="WGS Analysis Platform",
    description="全基因组测序分析平台",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url=None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(router, prefix="/api/v1")

# 静态文件
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", include_in_schema=False)
async def index():
    """返回前端页面"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"name": settings.app_name, "version": "0.1.0", "docs": "/api/docs"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}
