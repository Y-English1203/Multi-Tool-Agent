import os
from typing import TypedDict
from dotenv import load_dotenv
from openai import OpenAI
from langgraph.graph import StateGraph, END

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_OFFLINE"] = "1"
load_dotenv()
client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")


# ============ 状态定义 ============
class AgentState(TypedDict):
    question: str
    need_retrieval: bool
    context: str
    answer: str
    has_citation: bool
    retry_count: int
    max_retries: int
    vectorstore: object


# ============ 节点函数 ============
def classify_intent(state: AgentState) -> AgentState:
    """判断问题是否需要查文档"""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{
            "role": "user",
            "content": f"你是一个处理上传文档的助手。除非用户明显只是在打招呼或闲聊（比如'你好'、'今天天气怎么样'），否则一律回答 yes，去查询文档。\n\n用户问题：{state['question']}\n\n只回答 yes 或 no："
        }],
        temperature=0
    )
    text = response.choices[0].message.content.strip().lower()
    state["need_retrieval"] = "yes" in text
    return state


def retrieve(state: AgentState) -> AgentState:
    """检索文档，重试时自动加大检索范围"""
    if state["vectorstore"] is None:
        state["context"] = ""
        return state

    # 重试时把 k 从 8 增加到 15
    k = 8 if state["retry_count"] == 0 else 15
    retriever = state["vectorstore"].as_retriever(search_kwargs={"k": k})
    docs = retriever.invoke(state["question"])

    if not docs:
        state["context"] = ""
        return state

    parts = []
    for doc in docs:
        page = doc.metadata.get('page', '未知')
        if isinstance(page, int):
            page = page + 1
        parts.append(f"[第{page}页] {doc.page_content}")
    
    state["context"] = "\n\n".join(parts)
    
    # 调试语句：打印前100字，确认页码是否拼进去了
    print("【调试】检索到的上下文前100字：", state["context"][:100])
    
    return state

    # 重试时把 k 从 8 增加到 15
    k = 8 if state["retry_count"] == 0 else 15
    retriever = state["vectorstore"].as_retriever(search_kwargs={"k": k})
    docs = retriever.invoke(state["question"])

    if not docs:
        state["context"] = ""
        return state

    parts = []
    for doc in docs:
        page = doc.metadata.get('page', '未知')
        if isinstance(page, int):
            page = page + 1
        parts.append(f"[第{page}页] {doc.page_content}")
    state["context"] = "\n\n".join(parts)
    return state


def generate(state: AgentState) -> AgentState:
    """基于上下文生成回答"""
    if not state["context"]:
        state["answer"] = "文档中未找到相关内容。"
        state["has_citation"] = False
        return state

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": f"你是一个严格的文档助手。请严格根据以下文档内容回答问题。\n\n【强制要求】\n1. 只使用文档中提到的内容，不要编造。\n2. 回答末尾必须标注引用页码，格式严格为 [第X页]，例如 [第5页]。\n3. 如果文档未提及，请回答'文档中未提及'。\n\n【文档内容】\n{state['context']}"},
            {"role": "user", "content": state["question"]}
        ]
    )
    state["answer"] = response.choices[0].message.content
    state["has_citation"] = "[第" in state["answer"] and "页]" in state["answer"]
    return state


def direct_answer(state: AgentState) -> AgentState:
    """不检索，直接回答"""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": state["question"]}]
    )
    state["answer"] = response.choices[0].message.content
    state["has_citation"] = True  # 直接回答不参与重试
    return state


def retry_retrieve(state: AgentState) -> AgentState:
    """重试节点：增加计数"""
    state["retry_count"] += 1
    return state


# ============ 路由函数 ============
def route_after_classify(state: AgentState) -> str:
    return "retrieve" if state["need_retrieval"] else "direct_answer"


def route_after_generate(state: AgentState) -> str:
    if state["has_citation"] or state["retry_count"] >= state["max_retries"]:
        return "end"
    return "retry_retrieve"


# ============ 构建图 ============
def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_node("direct_answer", direct_answer)
    graph.add_node("retry_retrieve", retry_retrieve)

    graph.set_entry_point("classify_intent")

    graph.add_conditional_edges("classify_intent", route_after_classify, {
        "retrieve": "retrieve",
        "direct_answer": "direct_answer"
    })
    graph.add_edge("retrieve", "generate")
    graph.add_conditional_edges("generate", route_after_generate, {
        "end": END,
        "retry_retrieve": "retry_retrieve"
    })
    graph.add_edge("retry_retrieve", "retrieve")
    graph.add_edge("direct_answer", END)

    return graph.compile()


agent = build_graph()