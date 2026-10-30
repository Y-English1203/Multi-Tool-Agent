from supervisor_agent import (
    _dedupe_sources,
    _extract_json,
    _fallback_route,
    _follow_ups,
)


def test_extract_json_plain():
    assert _extract_json('{"intent": "sql"}')["intent"] == "sql"


def test_extract_json_fenced():
    text = '```json\n{"intent": "rag", "steps": []}\n```'
    assert _extract_json(text)["intent"] == "rag"


def test_extract_json_invalid():
    assert _extract_json("not json") == {}


def test_fallback_route_policy_before_sql():
    assert _fallback_route("年假有多少天？") == "rag"
    assert _fallback_route("销售额最高的品类") == "sql"
    assert _fallback_route("查询我的工单") == "ticket"


def test_follow_ups_are_short_and_unique():
    items = _follow_ups(["rag", "ticket"], "病假材料和工单")
    assert 1 <= len(items) <= 3
    assert len(items) == len(set(items))


def test_dedupe_sources():
    sources = [
        {"source": "手册", "page": 22, "content": "病假"},
        {"source": "手册", "page": 22, "content": "病假"},
        {"source": "手册", "page": 23, "content": "年假"},
    ]
    assert len(_dedupe_sources(sources)) == 2
