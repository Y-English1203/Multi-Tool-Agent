"""测试会话启动时确保业务库存在，避免依赖先手动启动服务。"""

import database
from seed_business_data import seed_business_db


def pytest_sessionstart(session):  # noqa: ARG001
    if database.table_counts().get("orders", 0) == 0:
        seed_business_db()
