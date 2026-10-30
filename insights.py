"""AI 经营洞察。

把确定性的经营统计交给大模型做解释、归因和建议，生成可直接展示的
结构化洞察。统计事实来自数据库，模型只负责“解读”，避免编造数字。
结果带 10 分钟缓存，避免每次打开工作台都重复调用模型。
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

import analytics
from database import query
from ticket_tools import ticket_stats

load_dotenv()

MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
CACHE_TTL_SECONDS = 600

_CACHE: dict[str, Any] = {
    "digest": None,
    "expires_at": 0.0,
    "payload": None,
}
_CACHE_LOCK = threading.Lock()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    timeout=60,
    max_retries=2,
)


def _category_growth() -> list[dict[str, Any]]:
    """最近两个月的品类销售额变化。"""
    months = [
        row["order_month"]
        for row in query(
            "SELECT DISTINCT order_month FROM v_sales_line ORDER BY order_month DESC LIMIT 2"
        )
    ]
    if len(months) < 2:
        return []

    current_month, previous_month = months[0], months[1]
    rows = query(
        """
        SELECT category, order_month, SUM(amount) AS revenue
        FROM v_sales_line
        WHERE status IN ('已完成','已发货') AND order_month IN (?, ?)
        GROUP BY category, order_month
        """,
        (current_month, previous_month),
    )

    pivot: dict[str, dict[str, float]] = {}
    for row in rows:
        category = row["category"]
        pivot.setdefault(category, {"current": 0.0, "previous": 0.0})
        if row["order_month"] == current_month:
            pivot[category]["current"] = float(row["revenue"] or 0)
        else:
            pivot[category]["previous"] = float(row["revenue"] or 0)

    growth = []
    for category, values in pivot.items():
        current = round(values["current"], 2)
        previous = round(values["previous"], 2)
        change = (
            round((current - previous) / previous * 100, 2) if previous else None
        )
        growth.append(
            {
                "category": category,
                "current": current,
                "previous": previous,
                "growth": change,
            }
        )
    return sorted(
        growth,
        key=lambda item: item["current"],
        reverse=True,
    )


def build_snapshot() -> dict[str, Any]:
    """汇总生成洞察所需的确定性事实。"""
    kpis = analytics.overview()
    trend = analytics.sales_trend(months=6)
    categories = analytics.category_sales()
    cities = analytics.city_sales()
    departments = analytics.department_sales()
    status = analytics.order_status()
    channels = analytics.channel_sales()
    company = analytics.company_profile()
    tickets = ticket_stats()

    current = trend[-1] if trend else {}
    previous = trend[-2] if len(trend) >= 2 else {}
    current_revenue = float(current.get("revenue") or 0)
    previous_revenue = float(previous.get("revenue") or 0)
    mom_growth = (
        round((current_revenue - previous_revenue) / previous_revenue * 100, 2)
        if previous_revenue
        else 0.0
    )

    total_orders = sum(int(item["orders"] or 0) for item in status) or 1
    refund_orders = sum(
        int(item["orders"] or 0) for item in status if item["status"] == "退款中"
    )

    return {
        "data_period": "2026-01 至 2026-10",
        "kpis": kpis,
        "latest_month": current.get("order_month"),
        "month_over_month": mom_growth,
        "trend": trend,
        "categories": categories[:6],
        "category_growth": _category_growth()[:6],
        "cities": cities[:5],
        "departments": departments,
        "order_status": status,
        "refund_rate": round(refund_orders / total_orders * 100, 2),
        "channels": channels[:5],
        "tickets": tickets,
        "company_profile": company[0] if company else None,
    }


def _fallback_insights(snapshot: dict[str, Any]) -> dict[str, Any]:
    """模型不可用时的规则洞察，仍然只使用真实统计值。"""
    kpis = snapshot["kpis"]
    categories = snapshot["categories"]
    cities = snapshot["cities"]
    growth = snapshot["month_over_month"]
    top_category = categories[0] if categories else {}
    top_city = cities[0] if cities else {}

    direction = "增长" if growth >= 0 else "下降"
    headline = (
        f"本月销售额环比{direction} {abs(growth):.1f}%，"
        f"{top_category.get('category', '头部品类')}仍是核心贡献"
    )
    summary = (
        f"有效销售额 {kpis['revenue']:,.2f} 元，有效订单 {kpis['orders']} 笔，"
        f"客单价 {kpis['aov']:,.2f} 元；退款率 {snapshot['refund_rate']:.2f}%。"
        f"销售额最高的品类为 {top_category.get('category', '—')}，"
        f"占比 {top_category.get('share', 0):.2f}%；"
        f"销售额最高的城市为 {top_city.get('city', '—')}。"
    )

    insights = []
    if top_category:
        insights.append(
            {
                "title": "品类集中度",
                "finding": (
                    f"{top_category['category']}贡献 {top_category['share']:.1f}% 的销售额，"
                    "头部品类对整体波动影响较大。"
                ),
                "evidence": (
                    f"{top_category['category']}销售额 {top_category['revenue']:,.2f} 元，"
                    f"销量 {top_category['units']} 件。"
                ),
                "action": "关注头部品类的库存与价格带，同时补充长尾品类以分散风险。",
                "severity": "medium",
            }
        )

    if categories and len(categories) > 1:
        fastest = max(
            snapshot.get("category_growth", []),
            key=lambda item: item.get("growth") or -999,
            default=None,
        )
        if fastest and fastest.get("growth") is not None:
            insights.append(
                {
                    "title": "品类增速",
                    "finding": (
                        f"{fastest['category']}环比变化 {fastest['growth']:+.1f}%，"
                        "是最近一个月波动最大的品类。"
                    ),
                    "evidence": (
                        f"本月 {fastest['current']:,.2f} 元，"
                        f"上月 {fastest['previous']:,.2f} 元。"
                    ),
                    "action": "复盘该品类的促销、库存和流量入口，判断增长是否可持续。",
                    "severity": "high" if abs(fastest["growth"]) >= 20 else "medium",
                }
            )

    if snapshot["refund_rate"] > 5:
        insights.append(
            {
                "title": "退款风险",
                "finding": f"退款中订单占比 {snapshot['refund_rate']:.2f}%，高于 5% 的观察线。",
                "evidence": "订单状态分布显示退款中订单需要重点跟进。",
                "action": "按品类和渠道下钻退款原因，优先处理高金额退款订单。",
                "severity": "high",
            }
        )
    else:
        insights.append(
            {
                "title": "履约质量",
                "finding": f"退款中订单占比 {snapshot['refund_rate']:.2f}%，整体处于可控范围。",
                "evidence": "订单状态分布中已完成与已发货订单占主要比例。",
                "action": "保持当前履约节奏，继续关注退款集中的品类。",
                "severity": "low",
            }
        )

    return {
        "headline": headline,
        "summary": summary,
        "insights": insights[:4],
        "risks": [
            f"退款率 {snapshot['refund_rate']:.2f}%",
            f"待处理/处理中工单 {snapshot['tickets'].get('open', 0)} 张",
        ],
        "confidence": 0.68,
        "fallback": True,
    }


def _llm_insights(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        return None

    data_text = json.dumps(snapshot, ensure_ascii=False, indent=2)[:9000]
    prompt = f"""你是企业经营分析专家。请基于下面的真实统计快照，生成一份简洁、可执行的经营洞察。

统计快照：
{data_text}

要求：
1. 只使用快照中的数字和事实，不要编造数据、时间或原因；
2. 找到 3—4 个值得管理者关注的现象，优先选择变化大、影响大的；
3. 每条洞察包含：发现、证据（引用具体数字）、建议动作、严重程度；
4. 区分事实与推测，推测必须标注“可能”；
5. 输出 JSON，不要输出 Markdown 代码块。

JSON 格式：
{{
  "headline": "一句话结论",
  "summary": "2—3 句总体判断",
  "insights": [
    {{
      "title": "洞察标题",
      "finding": "发现",
      "evidence": "数据证据",
      "action": "建议动作",
      "severity": "high|medium|low"
    }}
  ],
  "risks": ["风险1", "风险2"],
  "confidence": 0.0
}}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1200,
    )
    text = (response.choices[0].message.content or "").strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        import re

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(data, dict) or not data.get("headline"):
        return None

    raw_insights = data.get("insights")
    if not isinstance(raw_insights, list):
        raw_insights = []

    insights = []
    for item in raw_insights[:4]:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity", "medium")).lower()
        if severity not in ("high", "medium", "low"):
            severity = "medium"
        insights.append(
            {
                "title": str(item.get("title", "经营观察")),
                "finding": str(item.get("finding", "")),
                "evidence": str(item.get("evidence", "")),
                "action": str(item.get("action", "")),
                "severity": severity,
            }
        )

    if not insights:
        return None

    confidence = float(data.get("confidence", 0.8) or 0.8)
    return {
        "headline": str(data["headline"]),
        "summary": str(data.get("summary", "")),
        "insights": insights,
        "risks": [str(item) for item in data.get("risks", [])[:4]]
        if isinstance(data.get("risks"), list)
        else [],
        "confidence": max(0.0, min(1.0, confidence)),
        "fallback": False,
    }


def generate_insights(force: bool = False) -> dict[str, Any]:
    """生成或复用经营洞察。"""
    snapshot = build_snapshot()
    digest = hashlib.sha1(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    now = time.time()

    with _CACHE_LOCK:
        if (
            not force
            and _CACHE["payload"] is not None
            and _CACHE["digest"] == digest
            and now < _CACHE["expires_at"]
        ):
            return {**_CACHE["payload"], "cached": True}

    payload = None
    try:
        payload = _llm_insights(snapshot)
    except Exception as exc:
        print(f"[Insights] 模型洞察失败，使用规则洞察：{exc}")

    if payload is None:
        payload = _fallback_insights(snapshot)

    result = {
        **payload,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": MODEL,
        "data_digest": digest[:12],
        "data_period": snapshot["data_period"],
        "snapshot_summary": {
            "revenue": snapshot["kpis"]["revenue"],
            "orders": snapshot["kpis"]["orders"],
            "aov": snapshot["kpis"]["aov"],
            "mom_growth": snapshot["month_over_month"],
            "refund_rate": snapshot["refund_rate"],
        },
    }

    with _CACHE_LOCK:
        _CACHE["digest"] = digest
        _CACHE["expires_at"] = now + CACHE_TTL_SECONDS
        _CACHE["payload"] = result

    return {**result, "cached": False}


if __name__ == "__main__":
    print(json.dumps(generate_insights(force=True), ensure_ascii=False, indent=2))
