"""FastAPI 服务入口。

统一提供：
* Supervisor 多 Agent 对话接口；
* 业务数据仪表盘 / 分析 / 订单查询；
* 知识库文档管理、检索与重建索引；
* 工单 CRUD 与统计；
* 会话记忆管理；
* 前端静态资源托管。
"""

from __future__ import annotations

import logging
import os
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

import analytics
import database
from conversation_memory import (
    clear_user_history,
    conversation_stats,
    delete_session,
    get_history,
    get_session_messages,
    list_sessions,
    save_message,
)
from hybrid_retriever import HybridRetriever
from knowledge_base import KnowledgeBase
from text2sql import ask_database
from ticket_tools import (
    CATEGORIES,
    PRIORITIES,
    STATUSES,
    create_ticket,
    get_ticket,
    init_ticket_db,
    list_tickets,
    ticket_stats,
    update_ticket,
)
from supervisor_agent import SupervisorState, supervisor_agent

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / "frontend" / "dist"
LOG_DIR = BASE_DIR / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            LOG_DIR / "app.log",
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("multi_tool_agent")

VERSION = "2.0.0"
STARTED_AT = time.time()


# ============================================================
# 初始化
# ============================================================

def ensure_databases() -> None:
    """首次启动时自动生成演示数据，不覆盖已有业务数据。"""
    counts = database.table_counts()
    if counts.get("orders", 0) == 0:
        logger.info("业务数据库为空，正在生成演示数据...")
        from seed_business_data import main as seed_main

        seed_main()

    init_ticket_db()
    if ticket_stats()["total"] == 0:
        logger.info("工单数据库为空，正在生成演示工单...")
        from seed_business_data import seed_ticket_db

        seed_ticket_db()


def refresh_retriever(app: FastAPI) -> None:
    kb: KnowledgeBase = app.state.kb
    retriever = app.state.retriever

    if retriever is None:
        try:
            app.state.retriever = HybridRetriever(kb.get_vectorstore())
        except Exception as exc:
            logger.warning("重建混合检索器失败：%s", exc)
        return

    try:
        retriever.vectorstore = kb.get_vectorstore()
        retriever.refresh()
    except Exception as exc:
        logger.warning("刷新混合检索器失败：%s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_databases()

    kb = KnowledgeBase()
    kb.initialize()
    app.state.kb = kb

    retriever = None
    if kb.ready and kb.get_vectorstore() is not None:
        try:
            retriever = HybridRetriever(kb.get_vectorstore())
        except Exception as exc:
            logger.warning("加载混合检索器失败：%s", exc)
    app.state.retriever = retriever

    logger.info(
        "服务启动完成：知识库=%s，检索器=%s，版本=%s",
        "ready" if kb.ready else f"error({kb.error})",
        "ready" if retriever else "unavailable",
        VERSION,
    )
    yield
    logger.info("服务已停止")


app = FastAPI(
    title="Multi-Tool Agent",
    description=(
        "基于 LangGraph 的企业智能知识中台："
        "RAG 文档问答、Text-to-SQL 业务分析、工单管理与会话记忆。"
    ),
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_header(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())[:8]
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logger.exception("未处理异常：%s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "服务器内部错误，请稍后重试。",
            "error": str(exc),
            "path": request.url.path,
        },
    )


# ============================================================
# 请求模型
# ============================================================


class Question(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str = Field(default="default_user", max_length=64)
    session_id: str = Field(default="", max_length=64)


class SqlQuery(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class TicketCreate(BaseModel):
    user_id: str = Field(default="default_user", max_length=64)
    issue: str = Field(..., min_length=2, max_length=2000)
    category: str = "其他"
    priority: str = "中"
    assignee: str | None = None


class TicketUpdate(BaseModel):
    user_id: str = Field(default="default_user", max_length=64)
    status: str | None = None
    priority: str | None = None
    resolution: str | None = None
    assignee: str | None = None


def _clean_user(value: str | None) -> str:
    value = (value or "default_user").strip()
    return value[:64] or "default_user"


# ============================================================
# 健康检查 / 元信息
# ============================================================


@app.get("/api/health")
@app.get("/health")
def health(request: Request):
    kb: KnowledgeBase = request.app.state.kb
    kb_stats = kb.stats() if kb else {"ready": False, "error": "not_initialized"}

    try:
        counts = database.table_counts()
        db_ok = True
    except Exception as exc:
        counts = {}
        db_ok = False
        logger.warning("业务库健康检查失败：%s", exc)

    try:
        tickets = ticket_stats()
        ticket_ok = True
    except Exception as exc:
        tickets = {"total": 0, "error": str(exc)}
        ticket_ok = False

    try:
        memory = conversation_stats()
        memory_ok = True
    except Exception as exc:
        memory = {"error": str(exc)}
        memory_ok = False

    components = {
        "api": {"status": "ok"},
        "llm": {
            "status": "ok" if os.getenv("DEEPSEEK_API_KEY") else "missing_key",
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        },
        "business_db": {
            "status": "ok" if db_ok else "error",
            "orders": counts.get("orders", 0),
            "customers": counts.get("customers", 0),
            "products": counts.get("products", 0),
        },
        "knowledge": {
            "status": "ok" if kb_stats.get("ready") else "degraded",
            **kb_stats,
        },
        "tickets": {"status": "ok" if ticket_ok else "error", "total": tickets.get("total", 0)},
        "memory": {"status": "ok" if memory_ok else "error", **memory},
        "frontend": {
            "status": "ok" if DIST_DIR.exists() else "missing",
            "dist": str(DIST_DIR),
        },
    }

    status = "ok"
    if not db_ok or not ticket_ok or not kb_stats.get("ready"):
        status = "degraded"
    if not os.getenv("DEEPSEEK_API_KEY"):
        status = "degraded"

    return {
        "status": status,
        "version": VERSION,
        "uptime_seconds": round(time.time() - STARTED_AT, 1),
        "components": components,
    }


@app.get("/")
def root():
    if DIST_DIR.joinpath("index.html").exists():
        return FileResponse(DIST_DIR / "index.html")

    return {
        "system": "Multi-Tool Agent",
        "version": VERSION,
        "status": "running",
        "docs": "/docs",
        "frontend": "尚未构建，请运行 cd frontend && npm run build",
        "main_endpoint": "/ask/supervisor",
    }


# ============================================================
# 仪表盘 / 数据分析
# ============================================================


@app.get("/api/dashboard")
def dashboard():
    data = analytics.dashboard()
    data["tickets"] = ticket_stats()
    data["memory"] = conversation_stats()
    return data


@app.get("/api/analytics/overview")
def analytics_overview(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
):
    return analytics.overview(start=start, end=end)


@app.get("/api/analytics/trend")
def analytics_trend(
    months: int = Query(default=10, ge=1, le=36),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
):
    return analytics.sales_trend(months=months, start=start, end=end)


@app.get("/api/analytics/categories")
def analytics_categories(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
):
    return analytics.category_sales(start=start, end=end)


@app.get("/api/analytics/top-products")
def analytics_top_products(
    limit: int = Query(default=10, ge=1, le=50),
    metric: str = Query(default="revenue", pattern="^(revenue|units)$"),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
):
    return analytics.top_products(limit=limit, metric=metric, start=start, end=end)


@app.get("/api/analytics/cities")
def analytics_cities(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
):
    return analytics.city_sales(start=start, end=end)


@app.get("/api/analytics/departments")
def analytics_departments(
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
):
    return analytics.department_sales(start=start, end=end)


@app.get("/api/analytics/order-status")
def analytics_order_status():
    return analytics.order_status()


@app.get("/api/analytics/channels")
def analytics_channels():
    return analytics.channel_sales()


@app.get("/api/orders")
def orders(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    city: str | None = Query(default=None),
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
):
    return analytics.orders_page(
        page=page,
        size=size,
        status=status,
        keyword=keyword,
        city=city,
        start=start,
        end=end,
    )


@app.get("/api/products")
def products(limit: int = Query(default=60, ge=1, le=200)):
    return analytics.products_list(limit=limit)


@app.get("/api/filters")
def filters():
    return analytics.filter_options()


@app.post("/api/sql/query")
def sql_query(payload: SqlQuery):
    return ask_database(payload.question)


# ============================================================
# 知识库
# ============================================================


@app.get("/api/knowledge/stats")
def knowledge_stats(request: Request):
    return request.app.state.kb.stats()


@app.get("/api/knowledge/documents")
def knowledge_documents(request: Request):
    kb: KnowledgeBase = request.app.state.kb
    return {"documents": kb.list_documents(), "ready": kb.ready}


@app.get("/api/knowledge/search")
def knowledge_search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=500),
    top_k: int = Query(default=5, ge=1, le=20),
):
    kb: KnowledgeBase = request.app.state.kb
    if not kb.ready:
        raise HTTPException(status_code=503, detail=kb.error or "知识库尚未初始化")

    retriever = request.app.state.retriever
    if retriever is not None:
        results = retriever.retrieve_with_scores(q, top_k=top_k)
    else:
        results = kb.search(q, top_k=top_k)

    # metadata 只保留前端需要的字段，避免返回内部索引结构
    clean_results = [
        {
            "content": item.get("content", ""),
            "source": item.get("source", ""),
            "page": item.get("page"),
            "score": item.get("score", 0),
        }
        for item in results
    ]
    return {"query": q, "results": clean_results}


@app.post("/api/knowledge/documents")
async def knowledge_upload(
    request: Request,
    file: UploadFile = File(...),
):
    kb: KnowledgeBase = request.app.state.kb
    filename = file.filename or "document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="目前只支持 PDF 文档")

    content = await file.read()
    if len(content) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 30MB")
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")

    temp_path = BASE_DIR / f".upload-{uuid.uuid4().hex}.pdf"
    try:
        temp_path.write_bytes(content)
        document = kb.add_document(temp_path, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("上传文档失败")
        raise HTTPException(status_code=500, detail=f"文档索引失败：{exc}") from exc
    finally:
        if temp_path.exists():
            temp_path.unlink()

    refresh_retriever(request.app)
    return {"message": "文档已上传并建立索引", "document": document, "stats": kb.stats()}


@app.delete("/api/knowledge/documents/{doc_id}")
def knowledge_delete(request: Request, doc_id: str):
    kb: KnowledgeBase = request.app.state.kb
    if not kb.delete_document(doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    refresh_retriever(request.app)
    return {"message": "文档已删除", "stats": kb.stats()}


@app.post("/api/knowledge/rebuild")
def knowledge_rebuild(request: Request):
    kb: KnowledgeBase = request.app.state.kb
    if not kb.ready:
        raise HTTPException(status_code=503, detail=kb.error or "知识库尚未初始化")
    kb.rebuild()
    refresh_retriever(request.app)
    return {"message": "索引已重建", "stats": kb.stats()}


# ============================================================
# 工单
# ============================================================


@app.get("/api/tickets/meta")
def ticket_meta():
    return {
        "statuses": STATUSES,
        "priorities": PRIORITIES,
        "categories": CATEGORIES,
    }


@app.get("/api/tickets/stats")
def tickets_stats(user_id: str | None = Query(default=None)):
    return ticket_stats(user_id=_clean_user(user_id) if user_id else None)


@app.get("/api/tickets")
def tickets_list(
    user_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    items = list_tickets(
        user_id=_clean_user(user_id) if user_id else None,
        status=status,
        priority=priority,
        keyword=keyword,
        limit=limit,
    )
    return {"items": items, "total": len(items)}


@app.post("/api/tickets", status_code=201)
def tickets_create(payload: TicketCreate):
    try:
        ticket = create_ticket(
            user_id=_clean_user(payload.user_id),
            issue=payload.issue,
            priority=payload.priority,
            category=payload.category,
            assignee=payload.assignee,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ticket


@app.get("/api/tickets/{ticket_id}")
def tickets_get(ticket_id: int, user_id: str = Query(default="default_user")):
    ticket = get_ticket(ticket_id)
    if not ticket or ticket["user_id"] != _clean_user(user_id):
        raise HTTPException(status_code=404, detail="工单不存在")
    return ticket


@app.patch("/api/tickets/{ticket_id}")
def tickets_update(ticket_id: int, payload: TicketUpdate):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket["user_id"] != _clean_user(payload.user_id):
        raise HTTPException(status_code=403, detail="无权操作该工单")

    try:
        updated = update_ticket(
            ticket_id,
            status=payload.status,
            priority=payload.priority,
            resolution=payload.resolution,
            assignee=payload.assignee,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="工单不存在")
    return updated


# ============================================================
# 会话记忆
# ============================================================


@app.get("/api/sessions")
def sessions(user_id: str = Query(default="default_user")):
    return {"sessions": list_sessions(_clean_user(user_id))}


@app.get("/api/sessions/{session_id}/messages")
def session_messages(
    session_id: str,
    user_id: str = Query(default="default_user"),
):
    return {
        "session_id": session_id,
        "messages": get_session_messages(_clean_user(user_id), session_id),
    }


@app.delete("/api/sessions/{session_id}")
def session_delete(
    session_id: str,
    user_id: str = Query(default="default_user"),
):
    deleted = delete_session(_clean_user(user_id), session_id)
    return {"deleted": deleted}


@app.delete("/api/conversations")
def conversations_clear(user_id: str = Query(default="default_user")):
    deleted = clear_user_history(_clean_user(user_id))
    return {"deleted": deleted}


@app.get("/api/conversations/stats")
def conversations_stats(user_id: str | None = Query(default=None)):
    return conversation_stats(_clean_user(user_id) if user_id else None)


# ============================================================
# 主入口：Supervisor Multi-Agent
# ============================================================


@app.post("/ask/supervisor")
def ask_supervisor(q: Question, request: Request):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4())[:8])
    user_id = _clean_user(q.user_id)
    session_id = q.session_id or str(uuid.uuid4())

    logger.info(
        "[Trace: %s] [Session: %s] [User: %s] 收到请求：%s",
        trace_id,
        session_id,
        user_id,
        q.question,
    )

    try:
        history = get_history(user_id, session_id)

        initial_state: SupervisorState = {
            "question": q.question,
            "resolved_question": q.question,
            "user_id": user_id,
            "trace_id": trace_id,
            "history": history,
            "next_tool": "",
            "intent_reason": "",
            "answer": "",
            "tool_used": "",
            "data": {},
            "error": "",
            "retry_count": 0,
            "max_retries": 2,
            "retriever": request.app.state.retriever,
            "sources": [],
            "trace_steps": [],
        }

        result = supervisor_agent.invoke(initial_state)
        answer = result.get("answer", "")
        success = not bool(result.get("error"))

        if success:
            try:
                save_message(user_id, session_id, "user", q.question)
                save_message(user_id, session_id, "assistant", answer)
            except Exception:
                logger.exception("[Trace: %s] 保存会话记忆失败", trace_id)

        sources = result.get("sources", []) or []
        pages = sorted(
            {
                int(source["page"])
                for source in sources
                if isinstance(source, dict) and source.get("page") is not None
            }
        )

        logger.info(
            "[Trace: %s] 完成：tool=%s success=%s pages=%s",
            trace_id,
            result.get("tool_used", ""),
            success,
            pages,
        )

        return {
            "answer": answer,
            "tool_used": result.get("tool_used", ""),
            "sources": sources,
            "pages": pages,
            "data": result.get("data", {}) or {},
            "trace_steps": result.get("trace_steps", []),
            "intent_reason": result.get("intent_reason", ""),
            "trace_id": result.get("trace_id", trace_id),
            "session_id": session_id,
            "user_id": user_id,
            "success": success,
        }

    except Exception as exc:
        logger.exception("[Trace: %s] 请求处理失败", trace_id)
        return {
            "answer": "系统暂时无法处理该请求，请稍后再试。",
            "tool_used": "",
            "sources": [],
            "pages": [],
            "data": {},
            "trace_steps": [],
            "trace_id": trace_id,
            "session_id": session_id,
            "user_id": user_id,
            "success": False,
            "error": str(exc),
        }


# ============================================================
# 开发调试接口
# ============================================================


@app.post("/ask/rag")
def ask_rag(q: Question, request: Request):
    retriever = request.app.state.retriever
    if retriever is None:
        raise HTTPException(status_code=503, detail="知识库尚未就绪")

    docs = retriever.retrieve_with_scores(q.question, top_k=5)
    return {"question": q.question, "documents": docs, "count": len(docs)}


@app.post("/ask/data")
def ask_data(q: Question):
    return {"question": q.question, **ask_database(q.question)}


@app.post("/debug/route")
def debug_route(q: Question, request: Request):
    trace_id = str(uuid.uuid4())[:8]
    initial_state: SupervisorState = {
        "question": q.question,
        "resolved_question": q.question,
        "user_id": _clean_user(q.user_id),
        "history": get_history(_clean_user(q.user_id), q.session_id or "debug"),
        "trace_id": trace_id,
        "next_tool": "",
        "intent_reason": "",
        "answer": "",
        "tool_used": "",
        "data": {},
        "error": "",
        "retry_count": 0,
        "max_retries": 0,
        "retriever": request.app.state.retriever,
        "sources": [],
        "trace_steps": [],
    }
    result = supervisor_agent.invoke(initial_state)
    return {
        "question": q.question,
        "resolved_question": result.get("resolved_question"),
        "selected_tool": result.get("next_tool"),
        "intent_reason": result.get("intent_reason"),
        "trace_id": trace_id,
    }


# ============================================================
# 前端静态资源（必须最后注册）
# ============================================================

if DIST_DIR.joinpath("index.html").exists():
    assets_dir = DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith(("api/", "ask/", "debug/", "docs", "openapi.json", "health")):
            raise HTTPException(status_code=404, detail="接口不存在")

        candidate = DIST_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
