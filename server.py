import os
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from text2sql import text2sql
from hybrid_retriever import HybridRetriever
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# 1. 环境变量与初始化
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_OFFLINE"] = "1"
load_dotenv()
client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")

app = FastAPI()
# 存储对话历史，key 是 session_id，value 是消息列表
conversation_history = {}
MAX_HISTORY = 10  # 每个会话最多保留10轮对话

def load_vectorstore():
    reader = PdfReader("test.pdf")
    docs = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            from langchain_core.documents import Document
            docs.append(Document(page_content=text, metadata={"page": i}))
            
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=100)
    chunks = splitter.split_documents(docs)
    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh-v1.5")
    return Chroma.from_documents(chunks, embeddings)

vectorstore = load_vectorstore()
retriever = HybridRetriever(vectorstore)
# 2. 初始化向量库与检索器（假设 load_vectorstore 已经在其他地方定义好了，如果没有请自行补充）
vectorstore = load_vectorstore()
retriever = HybridRetriever(vectorstore)

class Question(BaseModel):
    question: str
    session_id: str = "default" 
# 3. RAG 检索接口（混合检索）
@app.post("/ask")
def ask(q: Question):
    docs = retriever.retrieve(q.question, top_k=5)
    context = "\n\n".join(docs)
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f"请严格根据以下文档内容回答问题，末尾标注引用页码。\n\n文档内容：\n{context}"},
            {"role": "user", "content": q.question}
        ]
    )
    return {"answer": response.choices[0].message.content}

# 4. SSE 流式接口
@app.post("/ask/stream")
async def ask_stream(q: Question):
    retriever_docs = retriever.retrieve(q.question, top_k=5)
    context = "\n\n".join(retriever_docs)

    async def event_generator():
        stream = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": f"请严格根据以下文档回答。\n\n文档内容：\n{context}"},
                {"role": "user", "content": q.question}
            ],
            stream=True
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield f"data: {chunk.choices[0].delta.content}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# 5. Text-to-SQL 数据查询接口
@app.post("/ask/data")
def ask_data(q: Question):
    answer = text2sql(q.question)
    return {"answer": answer}

# 6. Agent 自动路由接口
@app.post("/ask/auto")
def ask_auto(q: Question):
    """Agent 自动路由 + 多轮对话记忆 + 澄清机制"""
    session_id = q.session_id

    # 1. 获取历史
    if session_id not in conversation_history:
        conversation_history[session_id] = []
    history = conversation_history[session_id]

    # 2. 澄清机制：如果问题含模糊指代且无历史，主动反问
    ambiguous_words = ["它", "这个", "那个", "上面说的", "刚刚的"]
    if any(w in q.question for w in ambiguous_words) and len(history) == 0:
        return {
            "route": "clarify",
            "answer": "请问您指的是什么？可以补充一下具体对象吗？"
        }

    # 3. 后续路由逻辑不变
    route_response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{
            "role": "user",
            "content": f"判断这个问题是关于文档内容的，还是关于数据统计的。只回答'文档'或'数据'。\n\n问题：{q.question}"
        }],
        temperature=0
    )
    route = route_response.choices[0].message.content.strip()

    if "数据" in route:
        answer = text2sql(q.question)
        route_name = "text2sql"
    else:
        docs = retriever.retrieve(q.question, top_k=5)
        context = "\n\n".join(docs)
        messages = [
            {"role": "system", "content": f"请严格根据以下文档内容回答问题。\n\n文档内容：\n{context}"}
        ]
        messages.extend(history[-MAX_HISTORY:])
        messages.append({"role": "user", "content": q.question})
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages
        )
        answer = response.choices[0].message.content
        route_name = "rag"

    # 4. 存入历史
    history.append({"role": "user", "content": q.question})
    history.append({"role": "assistant", "content": answer})
    if len(history) > MAX_HISTORY * 2:
        conversation_history[session_id] = history[-MAX_HISTORY * 2:]

    return {"route": route_name, "answer": answer, "history_length": len(history) // 2}