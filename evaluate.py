"""端到端评估脚本。

对正在运行的 FastAPI 服务执行 eval_set.json 中的问题，统计：
* 工具路由是否正确；
* 关键词是否命中；
* LLM 裁判是否认为回答覆盖了关键信息；
* 分 RAG / SQL 统计准确率。

用法::

    python evaluate.py
    python evaluate.py --no-llm-judge
    python evaluate.py --limit 5 --output eval_results.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def llm_judge(client: OpenAI, question: str, answer: str, keywords: list[str]) -> bool:
    response = client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        messages=[
            {
                "role": "system",
                "content": (
                    "你是企业问答评测员。判断模型回答是否覆盖了问题所需的关键信息。"
                    "允许同义表达和数字格式差异。只回答“是”或“否”。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"问题：{question}\n"
                    f"参考答案关键词：{keywords}\n"
                    f"模型回答：{answer[:3000]}\n\n"
                    "回答是否覆盖了关键信息？"
                ),
            },
        ],
        temperature=0,
    )
    verdict = (response.choices[0].message.content or "").strip()
    return "是" in verdict or verdict.lower().startswith("yes")


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-Tool Agent 端到端评估")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--limit", type=int, default=0, help="只评估前 N 题")
    parser.add_argument("--no-llm-judge", action="store_true", help="只用关键词判定")
    parser.add_argument("--output", default="eval_results.json")
    args = parser.parse_args()

    eval_path = BASE_DIR / "eval_set.json"
    with eval_path.open("r", encoding="utf-8") as handle:
        eval_set = json.load(handle)
    if args.limit:
        eval_set = eval_set[: args.limit]

    client = None
    if not args.no_llm_judge:
        if not os.getenv("DEEPSEEK_API_KEY"):
            print("未配置 DEEPSEEK_API_KEY，自动降级为关键词判定。")
        else:
            client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                timeout=60,
            )

    try:
        requests.get(f"{args.base_url}/api/health", timeout=10).raise_for_status()
    except Exception as exc:
        print(f"无法连接服务 {args.base_url}：{exc}")
        print("请先运行：uvicorn server:app --host 127.0.0.1 --port 8000")
        return 2

    results = []
    category_stats: dict[str, dict[str, int]] = {}

    for index, item in enumerate(eval_set, start=1):
        question = item["question"]
        category = item.get("category", "rag")
        expected_tool = item.get("expected_tool")
        keywords = item.get("expected_keywords", [])

        session_id = f"eval-{uuid.uuid4().hex[:8]}"
        try:
            response = requests.post(
                f"{args.base_url}/ask/supervisor",
                json={
                    "question": question,
                    "user_id": "eval_user",
                    "session_id": session_id,
                },
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            print(f"[{index:02d}] 请求失败：{exc}")
            results.append(
                {
                    "question": question,
                    "category": category,
                    "passed": False,
                    "error": str(exc),
                }
            )
            category_stats.setdefault(category, {"total": 0, "passed": 0})
            category_stats[category]["total"] += 1
            continue

        answer = data.get("answer", "")
        tool = data.get("tool_used", "")
        keyword_hit = any(keyword in answer for keyword in keywords)
        tool_hit = not expected_tool or tool == expected_tool

        judge_hit = keyword_hit
        if client is not None:
            try:
                judge_hit = llm_judge(client, question, answer, keywords)
            except Exception as exc:
                print(f"  LLM 裁判失败，使用关键词结果：{exc}")

        passed = bool(judge_hit and tool_hit)
        pages = data.get("pages") or []
        results.append(
            {
                "question": question,
                "category": category,
                "answer": answer,
                "tool": tool,
                "expected_tool": expected_tool,
                "tool_hit": tool_hit,
                "keyword_hit": keyword_hit,
                "judge_hit": judge_hit,
                "pages": pages,
                "passed": passed,
            }
        )

        stats = category_stats.setdefault(category, {"total": 0, "passed": 0})
        stats["total"] += 1
        stats["passed"] += int(passed)

        mark = "✓" if passed else "✗"
        print(
            f"[{mark}] {index:02d}. {question} "
            f"(tool={tool}/{expected_tool}, keyword={keyword_hit})"
        )
        if not passed:
            print(f"     回答：{answer[:180].replace(chr(10), ' ')}")

    total = len(results)
    passed_total = sum(1 for item in results if item["passed"])
    summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "base_url": args.base_url,
        "total": total,
        "passed": passed_total,
        "accuracy": round(passed_total / total * 100, 1) if total else 0.0,
        "categories": {
            name: {
                **stats,
                "accuracy": round(stats["passed"] / stats["total"] * 100, 1)
                if stats["total"]
                else 0.0,
            }
            for name, stats in category_stats.items()
        },
        "results": results,
    }

    output_path = BASE_DIR / args.output
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 56)
    for name, stats in summary["categories"].items():
        print(
            f"{name.upper():4s}  {stats['passed']}/{stats['total']}  "
            f"= {stats['accuracy']}%"
        )
    print(f"TOTAL {passed_total}/{total} = {summary['accuracy']}%")
    print(f"结果已写入：{output_path}")
    return 0 if passed_total == total else 1


if __name__ == "__main__":
    sys.exit(main())
