"""工单 Agent。

把用户自然语言解析为结构化动作（查询 / 创建 / 查看状态 / 关闭），
再调用 ``ticket_tools``。所有查询和操作都限制在当前 ``user_id`` 下。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from ticket_tools import (
    CATEGORIES,
    PRIORITIES,
    STATUSES,
    create_ticket,
    format_ticket,
    format_ticket_list,
    get_ticket,
    list_tickets,
    update_ticket,
)

load_dotenv()

MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    timeout=60,
    max_retries=2,
)

CREATE_WORDS = (
    "创建工单", "新建工单", "提交工单", "我要报修", "帮我报修",
    "新建一个工单", "再创建一张", "再创建一个", "报修", "提个工单",
)
QUERY_WORDS = (
    "查询", "查看", "状态", "进度", "处理到哪", "怎么样了",
    "有没有处理", "我的工单", "工单列表",
)
CLOSE_WORDS = ("关闭工单", "取消工单", "撤销工单")


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
        return {}


def _guess_action(question: str) -> str:
    if any(word in question for word in CLOSE_WORDS):
        return "close"
    if any(word in question for word in CREATE_WORDS):
        return "create"
    if any(word in question for word in QUERY_WORDS):
        return "list"
    # 明确的“工单 3 状态”这类表达
    if re.search(r"工单\s*#?\s*(\d+)", question):
        return "status"
    return "unknown"


def parse_intent(question: str, user_id: str) -> dict[str, Any]:
    """LLM 解析工单意图，失败时回退到关键词规则。"""
    prompt = f"""你是企业工单 Agent 的意图解析器。

可选动作：
- list：查询当前用户的工单列表
- status：查询某一张工单的状态（需要 ticket_id）
- create：创建新工单（需要 issue，尽量提取完整问题描述）
- close：关闭/取消当前用户的某张工单（需要 ticket_id）
- unknown：意图不明确

字段要求：
- action：list / status / create / close / unknown
- ticket_id：整数或 null
- issue：字符串，创建工单时填写用户描述的问题
- category：从 {CATEGORIES} 中选择，无法判断填“其他”
- priority：从 {PRIORITIES} 中选择，无法判断填“中”

当前用户：{user_id}
用户问题：{question}

只输出一个 JSON 对象，不要解释。"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300,
        )
        data = _extract_json(response.choices[0].message.content or "")
    except Exception as exc:
        print(f"[Ticket] 意图解析失败，使用规则回退：{exc}")
        data = {}

    action = data.get("action")
    if action not in ("list", "status", "create", "close", "unknown"):
        action = _guess_action(question)

    ticket_id = data.get("ticket_id")
    if ticket_id is None:
        match = re.search(r"工单\s*#?\s*(\d+)", question)
        ticket_id = int(match.group(1)) if match else None

    category = data.get("category")
    if category not in CATEGORIES:
        category = "其他"

    priority = data.get("priority")
    if priority not in PRIORITIES:
        priority = "高" if any(word in question for word in ("紧急", "立刻", "马上", "严重")) else "中"

    issue = data.get("issue")
    if not isinstance(issue, str) or not issue.strip():
        issue = question.strip()

    return {
        "action": action,
        "ticket_id": ticket_id,
        "issue": issue.strip(),
        "category": category,
        "priority": priority,
    }


def handle_ticket(
    question: str,
    user_id: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    intent = parse_intent(question, user_id)
    action = intent["action"]
    result: dict[str, Any] = {
        "action": action,
        "ticket": None,
        "tickets": [],
        "success": True,
    }

    try:
        if action == "list":
            tickets = list_tickets(user_id=user_id)
            result["tickets"] = tickets
            result["answer"] = format_ticket_list(tickets, user_id)
            if tickets:
                pending = sum(
                    1 for ticket in tickets if ticket["status"] in ("待处理", "处理中")
                )
                result["answer"] += (
                    f"\n\n其中待处理/处理中共 {pending} 张。"
                    "你可以继续告诉我“查看工单 #编号”，查看单张工单详情。"
                )

        elif action == "status":
            ticket_id = intent.get("ticket_id")
            if not ticket_id:
                result["answer"] = "请告诉我工单编号，例如“查看工单 #3 的状态”。"
                result["success"] = False
                return result

            ticket = get_ticket(int(ticket_id))
            if not ticket or ticket["user_id"] != user_id:
                result["answer"] = (
                    f"未找到属于当前用户的工单 #{ticket_id}。"
                    "请确认编号，或先查询“我的工单”。"
                )
                result["success"] = False
                return result
            result["ticket"] = ticket
            result["answer"] = format_ticket(ticket)

        elif action == "create":
            ticket = create_ticket(
                user_id=user_id,
                issue=intent["issue"],
                priority=intent["priority"],
                category=intent["category"],
            )
            result["ticket"] = ticket
            result["answer"] = (
                f"工单已创建，编号 #{ticket['id']}。\n"
                f"问题：{ticket['issue']}\n"
                f"分类：{ticket['category']}，优先级：{ticket['priority']}，"
                f"当前状态：{ticket['status']}。\n"
                "我们会尽快安排处理，你稍后可以查询进度。"
            )

        elif action == "close":
            ticket_id = intent.get("ticket_id")
            if not ticket_id:
                result["answer"] = "请告诉我需要关闭的工单编号，例如“关闭工单 #3”。"
                result["success"] = False
                return result

            ticket = get_ticket(int(ticket_id))
            if not ticket or ticket["user_id"] != user_id:
                result["answer"] = f"未找到属于当前用户的工单 #{ticket_id}。"
                result["success"] = False
                return result

            if ticket["status"] in ("已解决", "已关闭"):
                result["answer"] = f"工单 #{ticket_id} 当前状态为“{ticket['status']}”，无需重复关闭。"
                result["ticket"] = ticket
                return result

            updated = update_ticket(
                int(ticket_id),
                status="已关闭",
                resolution="用户主动关闭",
            )
            result["ticket"] = updated
            result["answer"] = f"工单 #{ticket_id} 已关闭。如问题仍未解决，可以重新创建工单。"

        else:
            result["answer"] = (
                "请确认你的需求：\n"
                "1. 创建工单：直接描述故障或服务请求；\n"
                "2. 查询工单：回复“查询我的工单”；\n"
                "3. 查看单张工单：回复“查看工单 #编号”。"
            )
            result["success"] = False

    except Exception as exc:
        result["success"] = False
        result["answer"] = f"工单处理失败：{exc}"
        print(f"[Ticket] 执行失败：{exc}")

    return result
