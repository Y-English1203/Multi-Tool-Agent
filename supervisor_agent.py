import os
from typing import TypedDict

from dotenv import load_dotenv
from openai import OpenAI
from langgraph.graph import StateGraph, END

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# =========================
# Agent
# =========================

from agent_rag_v2 import run_rag
from text2sql import text2sql
from ticket_tools import (
    create_ticket,
    list_user_tickets,
    check_ticket_status
)


# =========================
# State
# =========================

class SupervisorState(TypedDict):
    question: str
    user_id: str
    trace_id: str

    # Supervisor 决定调用哪个 Agent
    next_tool: str

    # 最终回答
    answer: str

    # 实际调用的 Agent
    tool_used: str

    # 错误信息
    error: str

    # Supervisor 重试次数
    retry_count: int
    max_retries: int

    # HybridRetriever
    retriever: object


# =========================
# Supervisor
# =========================

def supervisor(state: SupervisorState) -> SupervisorState:
    """
    Supervisor 只负责：
    1. 分析用户问题
    2. 选择 RAG / SQL / Ticket
    3. 失败后重新路由
    """

    question = state["question"]

    # 如果上一个 Agent 执行失败
    if state.get("error"):
        print(
            f"[Trace: {state['trace_id']}] "
            f"⚠️ Agent 执行失败：{state['error']}"
        )

        if state["retry_count"] >= state["max_retries"]:
            state["answer"] = "系统暂时无法处理该请求，请稍后再试。"
            return state

        state["retry_count"] += 1
        state["error"] = ""

    prompt = f"""
你是一个企业智能助手系统中的 Supervisor。

你的任务不是回答问题，而是判断应该把问题交给哪个专业 Agent。

可选 Agent：

1. rag
适合：
- 企业文档
- PDF
- 制度
- 产品资料
- 项目资料
- 知识库问答
- 文档内容查询

2. sql
适合：
- 数据统计
- 数量
- 金额
- 排名
- 平均值
- 数据库查询
- 业务数据分析

3. ticket
适合：
- 创建工单
- 查询工单
- 工单状态
- 故障报修
- 服务请求

用户问题：
{question}

只允许回答：
rag
sql
ticket
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    tool = response.choices[0].message.content.strip().lower()

    if tool not in ["rag", "sql", "ticket"]:
        tool = "rag"

    state["next_tool"] = tool

    print(
        f"[Trace: {state['trace_id']}] "
        f"🧭 Supervisor 路由：{tool}"
    )

    return state


# =========================
# RAG Agent
# =========================

def rag_node(state: SupervisorState) -> SupervisorState:

    print(
        f"[Trace: {state['trace_id']}] "
        f"📚 调用 RAG Agent"
    )

    try:

        result = run_rag(
            question=state["question"],
            retriever=state["retriever"],
            max_retries=1
        )

        state["answer"] = result["answer"]

        state["tool_used"] = "rag"

        state["error"] = ""

    except Exception as e:

        print(
            f"[Trace: {state['trace_id']}] "
            f"❌ RAG Agent 错误：{e}"
        )

        state["error"] = str(e)

        state["answer"] = (
            "文档检索暂时不可用，请稍后再试。"
        )

    return state


# =========================
# Text-to-SQL Agent
# =========================

def sql_node(state: SupervisorState) -> SupervisorState:

    print(
        f"[Trace: {state['trace_id']}] "
        f"📊 调用 Text-to-SQL Agent"
    )

    try:

        answer = text2sql(
            state["question"]
        )

        state["answer"] = answer
        state["tool_used"] = "sql"
        state["error"] = ""

    except Exception as e:

        print(
            f"[Trace: {state['trace_id']}] "
            f"❌ SQL Agent 错误：{e}"
        )

        state["error"] = str(e)
        state["answer"] = ""

    return state


# =========================
# Ticket Agent
# =========================

def ticket_node(state: SupervisorState) -> SupervisorState:

    print(
        f"[Trace: {state['trace_id']}] "
        f"🎫 调用 Ticket Agent"
    )

    try:

        question = state["question"]
        user_id = state["user_id"]

        # 查询工单
        if "查询" in question or "状态" in question:

            answer = list_user_tickets(
                user_id
            )

        # 创建工单
        else:

            answer = create_ticket(
                user_id,
                question,
                priority="中"
            )

        state["answer"] = answer
        state["tool_used"] = "ticket"
        state["error"] = ""

    except Exception as e:

        print(
            f"[Trace: {state['trace_id']}] "
            f"❌ Ticket Agent 错误：{e}"
        )

        state["error"] = str(e)
        state["answer"] = ""

    return state


# =========================
# 路由
# =========================

def route_supervisor(
    state: SupervisorState
) -> str:

    return state["next_tool"]


def route_after_agent(
    state: SupervisorState
) -> str:

    # 成功
    if not state.get("error"):
        return "end"

    # 失败，但还有重试机会
    if state["retry_count"] < state["max_retries"]:
        return "retry"

    # 已经超过重试次数
    return "end"


# =========================
# 构建 Supervisor Graph
# =========================

def build_supervisor_graph():

    graph = StateGraph(
        SupervisorState
    )

    # Supervisor
    graph.add_node(
        "supervisor",
        supervisor
    )

    # 三个 Worker Agent
    graph.add_node(
        "rag_node",
        rag_node
    )

    graph.add_node(
        "sql_node",
        sql_node
    )

    graph.add_node(
        "ticket_node",
        ticket_node
    )

    # =====================
    # Entry
    # =====================

    graph.set_entry_point(
        "supervisor"
    )

    # =====================
    # Supervisor -> Agent
    # =====================

    graph.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "rag": "rag_node",
            "sql": "sql_node",
            "ticket": "ticket_node"
        }
    )

    # =====================
    # Agent -> END / Retry
    # =====================

    for node in [
        "rag_node",
        "sql_node",
        "ticket_node"
    ]:

        graph.add_conditional_edges(
            node,
            route_after_agent,
            {
                "end": END,
                "retry": "supervisor"
            }
        )

    return graph.compile()


# =========================
# Supervisor Agent
# =========================

supervisor_agent = build_supervisor_graph()