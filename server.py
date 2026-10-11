import os
import uuid
import uvicorn
import traceback
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

from hybrid_retriever import HybridRetriever
from text2sql import text2sql
from supervisor_agent import supervisor_agent, SupervisorState

from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from conversation_memory import get_history, save_message


# ============================================================
# 1. 环境变量
# ============================================================

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_OFFLINE"] = "1"

load_dotenv()


# ============================================================
# 2. FastAPI
# ============================================================

app = FastAPI(
    title="Multi-Tool Agent",
    description="基于 Multi-Agent 的企业智能助手系统",
    version="1.0.0"
)


# ============================================================
# 3. 加载知识库
# ============================================================

def load_vectorstore():

    reader = PdfReader("test.pdf")

    docs = []

    for i, page in enumerate(reader.pages):

        text = page.extract_text()

        if text and text.strip():

            from langchain_core.documents import Document

            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "page": i + 1
                    }
                )
            )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=100
    )

    chunks = splitter.split_documents(docs)

    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5"
    )

    return Chroma.from_documents(
        chunks,
        embeddings
    )


# ============================================================
# 4. 全局初始化
# ============================================================

vectorstore = load_vectorstore()

retriever = HybridRetriever(
    vectorstore
)


# ============================================================
# 5. 请求模型
# ============================================================


class Question(BaseModel):
    question: str
    user_id: str = "user_001"
    session_id: str | None = None


# ============================================================
# 6. 系统状态
# ============================================================

@app.get("/")
def root():

    return {
        "system": "Multi-Tool Agent",
        "status": "running",
        "main_endpoint": "/ask/supervisor"
    }


@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# ============================================================
# 7. ⭐ 主入口：Supervisor Multi-Agent
# ============================================================



@app.post("/ask/supervisor")
def ask_supervisor(q: Question):
    trace_id = str(uuid.uuid4())[:8]
    session_id = q.session_id or str(uuid.uuid4())

    print(
        f"[Trace: {trace_id}] "
        f"[Session: {session_id}] "
        f"收到用户请求：{q.question}"
    )

    try:
        history = get_history(q.user_id, session_id)

        initial_state: SupervisorState = {
            "question": q.question,
            "resolved_question": q.question,
            "user_id": q.user_id,
            "trace_id": trace_id,
            "history": history,
            "next_tool": "",
            "answer": "",
            "tool_used": "",
            "error": "",
            "retry_count": 0,
            "max_retries": 2,
            "retriever": retriever,
            "sources": []
        }

        result = supervisor_agent.invoke(initial_state)

        answer = result.get("answer", "")
        success = not bool(result.get("error"))

        # 只记录已完成的正常执行结果
        if success:
            save_message(
                q.user_id, session_id, "user", q.question
            )
            save_message(
                q.user_id, session_id, "assistant", answer
            )

        return {
            "answer": answer,
            "tool_used": result.get("tool_used", ""),
            "sources": result.get(
                "sources",
                []
            ),
            "trace_id": result.get("trace_id", trace_id),
            "session_id": session_id,
            "success": success,
        }

    except Exception as e:
        traceback.print_exc()

        return {
            "answer": "系统暂时无法处理该请求，请稍后再试。",
            "tool_used": "",
            "trace_id": trace_id,
            "session_id": session_id,
            "success": False,
            "error": str(e),
        }

# ============================================================
# 8. 开发调试：直接测试 RAG
# ============================================================

@app.post("/ask/rag")
def ask_rag(q: Question):

    docs = retriever.retrieve(
        q.question,
        top_k=5
    )

    return {

        "question": q.question,

        "documents": docs,

        "count": len(docs)
    }


# ============================================================
# 9. 开发调试：直接测试 Text-to-SQL
# ============================================================

@app.post("/ask/data")
def ask_data(q: Question):

    answer = text2sql(
        q.question
    )

    return {

        "question": q.question,

        "answer": answer,

        "tool_used": "sql"
    }


# ============================================================
# 10. 开发调试：直接测试 Supervisor 路由
# ============================================================

@app.post("/debug/route")
def debug_route(q: Question):

    trace_id = str(uuid.uuid4())[:8]

    initial_state: SupervisorState = {
    "question": q.question,
    "resolved_question": q.question,
    "user_id": q.user_id,
    "history": get_history(q.user_id, q.session_id or "debug"),
    "trace_id": trace_id,
    "next_tool": "",
    "answer": "",
    "tool_used": "",
    "error": "",
    "retry_count": 0,
    "max_retries": 0,
    "retriever": retriever,
    }

    result = supervisor_agent.invoke(
        initial_state
    )

    return {

        "question": q.question,

        "selected_tool": result.get(
            "next_tool"
        ),

        "trace_id": trace_id
    }


# ============================================================
# 11. 启动
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )