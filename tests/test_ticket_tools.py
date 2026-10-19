import shutil
import uuid
from pathlib import Path

import pytest

import ticket_tools


@pytest.fixture()
def isolated_tickets(monkeypatch):
    base = Path(__file__).resolve().parent / ".tmp" / uuid.uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ticket_tools, "DB_PATH", base / "tickets.db")
    ticket_tools.init_ticket_db()
    yield
    shutil.rmtree(base, ignore_errors=True)


def test_create_and_get_ticket(isolated_tickets):
    ticket = ticket_tools.create_ticket(
        "user_a", "电脑无法开机", priority="高", category="办公设备"
    )
    assert ticket["id"] > 0
    assert ticket["status"] == "待处理"
    assert ticket["user_id"] == "user_a"

    fetched = ticket_tools.get_ticket(ticket["id"])
    assert fetched["issue"] == "电脑无法开机"


def test_user_isolation(isolated_tickets):
    own = ticket_tools.create_ticket("user_a", "账号无法登录")
    ticket_tools.create_ticket("user_b", "打印机故障")

    user_a_tickets = ticket_tools.list_tickets(user_id="user_a")
    assert len(user_a_tickets) == 1
    assert user_a_tickets[0]["id"] == own["id"]


def test_update_ticket_status(isolated_tickets):
    ticket = ticket_tools.create_ticket("user_a", "VPN 无法连接")
    updated = ticket_tools.update_ticket(
        ticket["id"],
        status="处理中",
        assignee="IT服务台",
        resolution="正在排查",
    )
    assert updated["status"] == "处理中"
    assert updated["assignee"] == "IT服务台"


def test_invalid_status_rejected(isolated_tickets):
    ticket = ticket_tools.create_ticket("user_a", "故障")
    with pytest.raises(ValueError):
        ticket_tools.update_ticket(ticket["id"], status="不存在的状态")


def test_stats(isolated_tickets):
    ticket_tools.create_ticket("user_a", "问题一")
    second = ticket_tools.create_ticket("user_a", "问题二")
    ticket_tools.update_ticket(second["id"], status="已解决")

    stats = ticket_tools.ticket_stats("user_a")
    assert stats["total"] == 2
    assert stats["by_status"]["待处理"] == 1
    assert stats["by_status"]["已解决"] == 1
    assert stats["resolve_rate"] == pytest.approx(50.0)
