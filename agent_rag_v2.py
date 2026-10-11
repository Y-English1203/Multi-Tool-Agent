import os
from typing import TypedDict
import re
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


class AgentState(TypedDict):
    question: str
    need_retrieval: bool
    context: str
    answer: str
    has_citation: bool
    retry_count: int
    max_retries: int
    retriever: object
    history: list[dict[str, str]]
    search_question: str

def rewrite_question(state: AgentState) -> AgentState:
    """
    结合最近的对话历史，将当前追问改写成完整问题。
    不改变原始问题，只更新用于检索的问题。
    """

    history = state.get("history", [])
    question = state["question"]

    if not history:
        state["search_question"] = question
        return state

    recent_history = history[-6:]

    history_text = "\n".join(
        f"{item['role']}: {item['content']}"
        for item in recent_history
    )

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是企业文档检索中的问题改写助手。"
                        "请结合对话历史，将用户当前问题改写成一个"
                        "语义完整、可以独立用于文档检索的问题。"
                        "保留用户当前问题的真实意图，不要回答问题，"
                        "不要添加历史中没有依据的事实。"
                        "如果当前问题本身已经完整，就原样保留。"
                        "只输出改写后的问题。"
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"最近的对话历史：\n{history_text}\n\n"
                        f"当前问题：{question}"
                    )
                }
            ],
            temperature=0
        )

        rewritten = response.choices[0].message.content.strip()

        state["search_question"] = rewritten or question

        print(
            "[RAG] 检索问题改写："
            f"{question} -> {state['search_question']}"
        )

    except Exception as e:
        print(f"[RAG] 问题改写失败，使用原问题：{e}")
        state["search_question"] = question

    return state


def classify_intent(state: AgentState) -> AgentState:
    """结合改写问题和历史判断是否需要检索。"""

    question = state["question"]
    search_question = state.get("search_question", question)
    history = state.get("history", [])[-6:]

    history_text = "\n".join(
        f"{item['role']}: {item['content']}"
        for item in history
    )

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": (
                    "你是企业文档问答系统的意图分类器。"
                    "需要查询企业制度、PDF、产品资料、"
                    "项目资料或知识库时返回 yes。"
                    "普通闲聊和打招呼返回 no。"
                    "对于依赖历史的追问，结合历史和完整问题判断。"
                    "只允许输出 yes 或 no。"
                )
            },
            {
                "role": "user",
                "content": (
                    f"最近历史：\n{history_text or '暂无'}\n\n"
                    f"原始问题：{question}\n"
                    f"完整检索问题：{search_question}"
                )
            }
        ],
        temperature=0
    )

    text = (
        response.choices[0].message.content or ""
    ).strip().lower()

    state["need_retrieval"] = text.startswith("yes")
    return state


def retrieve(state: AgentState) -> AgentState:
    """使用 HybridRetriever 检索，并保留真实页码。"""

    retriever = state["retriever"]

    top_k = 5 if state["retry_count"] == 0 else 10

    try:
        search_question = state.get(
            "search_question",
            state["question"]
)
        print(f"[RAG] 原始问题：{state['question']}")
        print(f"[RAG] 改写后问题：{search_question}")
        docs = retriever.retrieve(
            search_question,
            top_k=top_k
)

        if not docs:
            state["context"] = ""
            return state

        parts = []

        for index, doc in enumerate(docs):
            # 明确提取正文和页码 metadata
            page = doc.metadata.get("page")

            if page is None:
                page_label = "页码未知"
            else:
                # 当前 PDF 加载逻辑使用 page=i+1 时，
                # metadata 已经是从 1 开始的页码，不要再次 +1。
                page_label = f"第{page}页"

            parts.append(
                f"[检索结果{index + 1}]\n"
                f"[来源：{page_label}]\n"
                f"{doc.page_content}"
            )

        state["context"] = "\n\n".join(parts)

        print(f"[RAG] 检索结果数量：{len(docs)}")
        print(f"[RAG] 当前 Top-K：{top_k}")

        for index, doc in enumerate(docs):
            print(
                f"[RAG] 结果{index + 1}页码："
                f"{doc.metadata.get('page', '未知')}"
            )

    except Exception as e:
        print(f"[RAG] 检索失败：{e}")
        state["context"] = ""

    return state



def generate(state: AgentState) -> AgentState:
    """根据检索结果生成回答，并校验引用页码。"""

    if not state["context"]:
        state["answer"] = "文档中未找到相关内容。"
        state["has_citation"] = False
        return state

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": f"""
你是一个严格的企业文档问答助手。

请严格根据提供的文档内容回答。

规则：
1. 不允许编造文档中没有的信息。
2. 如果文档中没有答案，回答“文档中未提及。”
3. 只允许引用检索结果中明确提供的页码。
4. 引用格式为 [第X页]，X 必须来自实际检索结果。
5. 不要猜测页码。
6. 如果多个页面支持答案，可以引用多个页面。
7. 不要把检索结果编号当作 PDF 页码。

检索结果：
{state["context"]}
"""
            },
            {
                "role": "user",
                "content": state.get(
                "search_question",
                state["question"]
                )           
            }
        ],
        temperature=0
    )

    answer = response.choices[0].message.content.strip()
    state["answer"] = answer

    # 从检索上下文中提取真实可用页码
    allowed_pages = set(
        re.findall(
            r"\[来源：第(\d+)页\]",
            state["context"]
        )
    )

    # 提取答案实际引用的页码
    cited_pages = re.findall(
        r"\[第(\d+)页\]",
        answer
    )

    # 必须有引用，并且所有引用都来自检索结果
    valid_citation = (
        bool(cited_pages)
        and set(cited_pages).issubset(allowed_pages)
    )

    state["has_citation"] = valid_citation

    if not valid_citation:
        print("[RAG] 引用校验未通过")
        print(f"[RAG] 可用页码：{sorted(allowed_pages)}")
        print(f"[RAG] 回答引用：{cited_pages}")

    # 引用不可靠时，不向用户返回未经验证的答案
        state["answer"] = (
        "本次回答未能通过引用校验，"
        "暂时无法可靠确认答案及其来源，请稍后重试。"
    )
    else:
        print(f"[RAG] 引用校验通过：{sorted(set(cited_pages))}")

    return state



def direct_answer(state: AgentState) -> AgentState:
    """不检索文档时，结合近期历史进行普通对话。"""

    history = state.get("history", [])[-6:]

    messages = [
        {
            "role": "system",
            "content": (
                "你是企业智能助手。"
                "可以利用历史理解用户的追问，"
                "但不能将历史中的未经验证内容当作企业制度事实。"
                "涉及企业制度或业务数据的问题应交由专业工具处理。"
            )
        }
    ]

    for item in history:
        role = item.get("role")
        content = item.get("content", "")

        if role in ("user", "assistant") and content:
            messages.append({
                "role": role,
                "content": content[:2000]
            })

    messages.append({
        "role": "user",
        "content": state["question"]
    })

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0
    )

    state["answer"] = (
        response.choices[0].message.content or ""
    ).strip()

    state["has_citation"] = True
    return state


def retry_retrieve(state: AgentState) -> AgentState:
    """
    增加检索范围。
    """

    state["retry_count"] += 1

    return state


def route_after_classify(state: AgentState) -> str:

    if state["need_retrieval"]:
        return "retrieve"

    return "direct_answer"


def route_after_generate(state: AgentState) -> str:

    if (
        state["has_citation"]
        or state["retry_count"]
        >= state["max_retries"]
    ):
        return "end"

    return "retry_retrieve"


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("rewrite_question", rewrite_question)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_node("direct_answer", direct_answer)
    graph.add_node("retry_retrieve", retry_retrieve)

    graph.set_entry_point("rewrite_question")

    graph.add_edge("rewrite_question", "classify_intent")

    graph.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {
            "retrieve": "retrieve",
            "direct_answer": "direct_answer"
        }
    )

    graph.add_edge("retrieve", "generate")

    graph.add_conditional_edges(
        "generate",
        route_after_generate,
        {
            "end": END,
            "retry_retrieve": "retry_retrieve"
        }
    )

    graph.add_edge("retry_retrieve", "retrieve")
    graph.add_edge("direct_answer", END)

    return graph.compile()


agent = build_graph()
def run_rag(
    question: str,
    retriever,
    max_retries: int = 1,
    history: list[dict[str, str]] | None = None
):
    """
    RAG Agent 对外统一调用入口。
    支持传入对话历史，供后续追问改写使用。
    """

    initial_state: AgentState = {
        "question": question,
        "need_retrieval": True,
        "context": "",
        "answer": "",
        "has_citation": False,
        "retry_count": 0,
        "max_retries": max_retries,
        "retriever": retriever,
        "search_question": question,
        "history": history or []
    }

    return agent.invoke(initial_state)