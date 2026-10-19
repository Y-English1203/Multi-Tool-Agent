"""初始化演示数据库。

用法::

    python init_db.py

会重建 ``business.db``（业务数据）和 ``tickets.db``（工单数据）。
两个库都使用固定随机种子，重复运行结果一致。
"""

from seed_business_data import main

if __name__ == "__main__":
    main()
