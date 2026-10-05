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
    next_tool: str       # rag / sql / ticket
    answer: str
    tool_used: str
    ticket_action: str   # create / query / escalate
    history: list

# ============ Supervisor 节点 ============
def supervisor(state: SupervisorState) -> SupervisorState:
    """主管：根据用户问题决定调用哪个工具"""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{
            "role": "user",
            "content": f"""你是一个任务调度主管。请判断用户的问题应该调用哪个工具，只回答一个词：
- rag：关于文档内容、知识库、资料查询
- sql：关于数据统计、销量、订单、金额
- ticket：关于创建工单、投诉、退款、查询工单状态

用户问题：{state['question']}
只回答：rag / sql / ticket"""
        }],
        temperature=0
    )
    tool = response.choices[0].message.content.strip().lower()
    state["next_tool"] = tool if tool in ["rag", "sql", "ticket"] else "rag"
    return state

# ============ 工具节点 ============
def rag_node(state: SupervisorState) -> SupervisorState:
    print(f"[Trace: {state['trace_id']}] 📚 调用 RAG 检索")
    # 注意：HybridRetriever 需要在外部初始化后传入，这里简化处理，实际可以传入
    # 为了简化，这里直接用 text2sql 的 client 调一次 LLM 模拟
    # 实际上你应该复用 server.py 里的 retriever
    state["tool_used"] = "rag"
    state["answer"] = "（RAG 检索结果，请接入 retriever）"
    return state

def sql_node(state: SupervisorState) -> SupervisorState:
    print(f"[Trace: {state['trace_id']}] 📊 调用 Text-to-SQL")
    state["tool_used"] = "sql"
    state["answer"] = text2sql(state["question"])
    return state

def ticket_node(state: SupervisorState) -> SupervisorState:
    print(f"[Trace: {state['trace_id']}] 🎫 调用工单工具")
    state["tool_used"] = "ticket"
    if "查询" in state["question"] or "状态" in state["question"]:
        state["answer"] = list_user_tickets(state["user_id"])
    else:
        state["answer"] = create_ticket(state["user_id"], state["question"], priority="中")
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