import os
from typing import TypedDict

from dotenv import load_dotenv
from openai import OpenAI
from langgraph.graph import StateGraph, END

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_OFFLINE"] = "1"

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


# ============================================================
# State
# ============================================================

class AgentState(TypedDict):
    question: str
    context: str
    answer: str

    has_citation: bool

    retry_count: int
    max_retries: int

    # 使用项目现有的 HybridRetriever
    retriever: object


# ============================================================
# 1. 检索
# ============================================================

def retrieve(state: AgentState) -> AgentState:

    retriever = state["retriever"]

    # 第一次检索 5 条
    # 重试时扩大到 10 条
    top_k = 5 if state["retry_count"] == 0 else 10

    try:
        docs = retriever.retrieve(
            state["question"],
            top_k=top_k
        )

        if not docs:
            state["context"] = ""
            return state

        parts = []

        for index, doc in enumerate(docs):

            parts.append(
                f"[检索结果 {index + 1}]\n{doc}"
            )

        state["context"] = "\n\n".join(parts)

        print(
            f"[RAG] 检索结果数量：{len(docs)}"
        )

        print(
            f"[RAG] 当前 Top-K：{top_k}"
        )

        print(
            "[RAG] 上下文前200字：",
            state["context"][:200]
        )

    except Exception as e:

        print(
            f"[RAG] 检索失败：{e}"
        )

        state["context"] = ""

    return state


# ============================================================
# 2. 生成答案
# ============================================================

def generate(state: AgentState) -> AgentState:

    context = state["context"]

    if not context:

        state["answer"] = (
            "文档中未找到相关内容。"
        )

        state["has_citation"] = False

        return state

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": f"""
你是一个严格的企业知识库问答助手。

请严格根据下面的检索内容回答用户问题。

要求：

1. 只能使用检索内容中的信息。
2. 不允许编造。
3. 如果检索内容无法回答问题，
   请回答“文档中未提及”。
4. 回答简洁、准确。
5. 不要暴露“检索结果1”等内部信息。

检索内容：

========================

{context}

========================
"""
            },
            {
                "role": "user",
                "content": state["question"]
            }
        ],
        temperature=0.1
    )

    answer = (
        response.choices[0]
        .message.content
        .strip()
    )

    state["answer"] = answer

    # 当前 HybridRetriever 返回纯文本，
    # 所以第一版暂时通过回答内容判断是否包含引用。
    state["has_citation"] = (
        "[第" in answer
        and "页]" in answer
    )

    return state


# ============================================================
# 3. 重试
# ============================================================

def retry_retrieve(state: AgentState) -> AgentState:

    state["retry_count"] += 1

    print(
        f"[RAG] 开始第 "
        f"{state['retry_count']} 次重新检索"
    )

    return state


# ============================================================
# 4. 生成后路由
# ============================================================

def route_after_generate(
    state: AgentState
) -> str:

    # 已经有引用
    if state["has_citation"]:
        return "end"

    # 达到最大重试次数
    if (
        state["retry_count"]
        >= state["max_retries"]
    ):
        return "end"

    # 没有引用 -> 重新检索
    return "retry"


# ============================================================
# 5. 构建 RAG Graph
# ============================================================

def build_graph():

    graph = StateGraph(AgentState)

    graph.add_node(
        "retrieve",
        retrieve
    )

    graph.add_node(
        "generate",
        generate
    )

    graph.add_node(
        "retry_retrieve",
        retry_retrieve
    )

    graph.set_entry_point(
        "retrieve"
    )

    graph.add_edge(
        "retrieve",
        "generate"
    )

    graph.add_conditional_edges(
        "generate",
        route_after_generate,
        {
            "end": END,
            "retry": "retry_retrieve"
        }
    )

    graph.add_edge(
        "retry_retrieve",
        "retrieve"
    )

    return graph.compile()


agent = build_graph()


# ============================================================
# 6. 对外统一接口
# ============================================================

def run_rag(
    question: str,
    retriever,
    max_retries: int = 1
):

    initial_state: AgentState = {

        "question": question,

        "context": "",

        "answer": "",

        "has_citation": False,

        "retry_count": 0,

        "max_retries": max_retries,

        "retriever": retriever
    }

    result = agent.invoke(
        initial_state
    )

    return result