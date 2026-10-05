import os
from typing import TypedDict, Literal
from dotenv import load_dotenv
from openai import OpenAI
from langgraph.graph import StateGraph, END

load_dotenv()
client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")

# 导入你现有的工具
from hybrid_retriever import HybridRetriever
from text2sql import text2sql
from ticket_tools import create_ticket, list_user_tickets, check_ticket_status
# ============ 状态定义 ============
class SupervisorState(TypedDict):
    question: str
    user_id: str
    trace_id: str
    next_tool: str
    answer: str
    tool_used: str
    error: str
    retry_count: int
    max_retries: int
    retriever: object   # 新增：传入 retriever  # 新增：最大重试次数

# ============ Supervisor 节点 ============
def supervisor(state: SupervisorState) -> SupervisorState:
    # 如果有错误且未超过重试上限，重新路由
    if state.get("error") and state.get("retry_count", 0) < state.get("max_retries", 2):
        print(f"[Trace: {state['trace_id']}] ⚠️ 工具执行失败，准备重试...")
        state["retry_count"] += 1
        state["error"] = ""
        # 重新判断工具
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"用户问题：{state['question']}\n只回答：rag / sql / ticket"}],
            temperature=0
        )
        tool = response.choices[0].message.content.strip().lower()
        state["next_tool"] = tool if tool in ["rag", "sql", "ticket"] else "rag"
        return state

    # 正常判断
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": f"判断问题类型，只回答：rag / sql / ticket。\n\n用户问题：{state['question']}"}],
        temperature=0
    )
    tool = response.choices[0].message.content.strip().lower()
    state["next_tool"] = tool if tool in ["rag", "sql", "ticket"] else "rag"
    return state
# ============ 工具节点 ============
def rag_node(state: SupervisorState) -> SupervisorState:
    print(f"[Trace: {state['trace_id']}] 📚 调用 RAG 检索")
    try:
        # 1. 从 state 里取出 retriever，做混合检索
        docs = state["retriever"].retrieve(state["question"], top_k=5)
        context = "\n\n".join(docs)

        # 2. 把检索结果拼成上下文，发给大模型生成回答
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": f"请严格根据以下文档内容回答问题，末尾标注引用页码。\n\n文档内容：\n{context}"},
                {"role": "user", "content": state["question"]}
            ]
        )

        state["answer"] = response.choices[0].message.content
        state["tool_used"] = "rag"
        state["error"] = ""
    except Exception as e:
        state["error"] = str(e)
        state["answer"] = "文档检索暂时不可用，请稍后再试。"
    return state

def sql_node(state: SupervisorState) -> SupervisorState:
    print(f"[Trace: {state['trace_id']}] 📊 调用 Text-to-SQL")
    try:
        state["answer"] = text2sql(state["question"])
        state["tool_used"] = "sql"
        state["error"] = ""
    except Exception as e:
        state["error"] = str(e)
        state["answer"] = "数据查询暂时不可用，请稍后再试。"
    return state

def ticket_node(state: SupervisorState) -> SupervisorState:
    print(f"[Trace: {state['trace_id']}] 🎫 调用工单工具")
    try:
        if "查询" in state["question"] or "状态" in state["question"]:
            state["answer"] = list_user_tickets(state["user_id"])
        else:
            state["answer"] = create_ticket(state["user_id"], state["question"], priority="中")
        state["tool_used"] = "ticket"
        state["error"] = ""
    except Exception as e:
        state["error"] = str(e)
        state["answer"] = "工单服务暂时不可用，请稍后再试。"
    return state

# ============ 路由 ============
def route_supervisor(state: SupervisorState) -> str:
    return state["next_tool"]

# ============ 构建图 ============
def build_supervisor_graph():
    graph = StateGraph(SupervisorState)
    graph.add_node("supervisor", supervisor)
    graph.add_node("rag_node", rag_node)
    graph.add_node("sql_node", sql_node)
    graph.add_node("ticket_node", ticket_node)

    graph.set_entry_point("supervisor")
    graph.add_conditional_edges("supervisor", route_supervisor, {
        "rag": "rag_node",
        "sql": "sql_node",
        "ticket": "ticket_node"
    })
    graph.add_edge("rag_node", END)
    graph.add_edge("sql_node", END)
    graph.add_edge("ticket_node", END)

    return graph.compile()

supervisor_agent = build_supervisor_graph()