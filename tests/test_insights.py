from insights import _fallback_insights, build_snapshot


def test_snapshot_contains_business_facts():
    snapshot = build_snapshot()
    assert snapshot["kpis"]["revenue"] > 0
    assert snapshot["categories"]
    assert snapshot["cities"]
    assert "month_over_month" in snapshot
    assert "refund_rate" in snapshot
    assert "tickets" in snapshot


def test_fallback_insights_are_grounded():
    snapshot = build_snapshot()
    result = _fallback_insights(snapshot)
    assert result["headline"]
    assert result["summary"]
    assert len(result["insights"]) >= 2
    assert all(item["evidence"] for item in result["insights"])
    assert result["fallback"] is True
