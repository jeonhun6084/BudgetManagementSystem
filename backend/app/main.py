from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

from .database.db import init_db
from .routers import transactions, salary, expenses, stocks

app = FastAPI(title="個人予算管理システム", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions.router)
app.include_router(salary.router)
app.include_router(expenses.router)
app.include_router(stocks.router)

# フロントエンド静的ファイルの提供
frontend_dir = Path(__file__).parent.parent.parent / "frontend"
static_dir = frontend_dir / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = frontend_dir / "templates" / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>予算管理システム起動中...</h1>")


@app.get("/health")
async def health():
    return {"status": "ok"}
