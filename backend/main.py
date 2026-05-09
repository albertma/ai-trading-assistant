"""
AI投研助手 - FastAPI主入口（含前端静态文件服务）
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path

from backend.config import HOST, PORT, DEBUG
from backend.routers import market, positions, analysis, risk, reports, fundamental, profile, watchlist, chat, stock_info, risk_rules, knowledge_graph, mental_models

app = FastAPI(
    title="AI投研助手",
    description="金融AI投研助理 — 复盘、持仓、分析、风控",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== API 路由（优先于静态文件） ==========
app.include_router(market.router, prefix="/api/v1/market", tags=["市场"])
app.include_router(positions.router, prefix="/api/v1/positions", tags=["持仓"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["分析"])
app.include_router(risk.router, prefix="/api/v1/risk", tags=["风控"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["报告"])
app.include_router(fundamental.router, prefix="/api/v1/fundamental", tags=["基本面"])
app.include_router(profile.router, prefix="/api/v1/profile", tags=["档案"])
app.include_router(watchlist.router, prefix="/api/v1/watchlist", tags=["观察池"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["AI聊天"])
app.include_router(stock_info.router, prefix="/api/v1/stock-info", tags=["个股资料"])
app.include_router(risk_rules.router, prefix="/api/v1/risk-rules", tags=["风控规则"])
app.include_router(knowledge_graph.router, prefix="/api/v1/kg", tags=["知识图谱"])
app.include_router(mental_models.router, prefix="/api/v1/mental", tags=["思维模型"])

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api")
def api_info():
    return {"service": "AI投研助手", "version": "0.1.0", "status": "running"}

# ========== 前端静态文件（兜底） ==========
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists() and (frontend_dist / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        # 非前端路由的路径直接404
        index_path = frontend_dist / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return JSONResponse({"error": "frontend not built"}, status_code=503)
else:
    print("⚠️ 前端静态文件未构建，请先运行: cd frontend && npm run build")
