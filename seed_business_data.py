"""生成企业智能知识中台演示所需的业务数据库。

数据口径
--------
* 商品品类参照京东商城公开的频道分类（手机通讯、电脑办公、家用电器、
  数码配件、家居日用、食品饮料、美妆个护、服饰鞋包、母婴玩具、运动户外）。
* 部分商品参考价来自公开商品页面（仅用于演示，非实时价格）。
* 客户、员工、订单为固定随机种子生成的模拟数据，可重复重建，
  不对应任何真实个人或真实交易。
* 时间窗口固定为 2026-01-01 至 2026-10-18，与项目评测集的
  “本月 / 上个月”口径保持一致。

运行方式::

    python seed_business_data.py
    # 或
    python init_db.py
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "business.db"

RANDOM_SEED = 20261019
DATA_START = date(2026, 1, 1)
DATA_END = date(2026, 10, 18)
"数据截止日。评测和前端中的“今天”以项目运行日期为准，但样例数据覆盖此区间。"

# ---------------------------------------------------------------------------
# 组织 / 人员
# ---------------------------------------------------------------------------

DEPARTMENTS = [
    (1, "3C数码事业部", "北京", "张伟"),
    (2, "电脑办公事业部", "北京", "刘洋"),
    (3, "家电事业部", "上海", "孙强"),
    (4, "大商超事业部", "上海", "郑洁"),
    (5, "时尚居家事业部", "广州", "黄勇"),
    (6, "母婴运动事业部", "成都", "高敏"),
]

EMPLOYEES = [
    (1, "李明", 1, "高级销售经理", "2019-03-11", "北京"),
    (2, "王芳", 1, "销售代表", "2021-07-05", "北京"),
    (3, "陈晨", 2, "销售经理", "2020-05-18", "北京"),
    (4, "赵磊", 2, "销售代表", "2022-09-01", "北京"),
    (5, "周婷", 3, "销售经理", "2018-11-12", "上海"),
    (6, "吴昊", 3, "销售代表", "2021-02-22", "上海"),
    (7, "徐鹏", 4, "销售代表", "2020-08-15", "上海"),
    (8, "马丽", 4, "销售经理", "2019-06-24", "上海"),
    (9, "林静", 5, "销售代表", "2022-03-07", "广州"),
    (10, "何杰", 5, "销售经理", "2020-10-19", "广州"),
    (11, "罗雪", 6, "销售代表", "2021-12-01", "成都"),
    (12, "谢峰", 6, "销售经理", "2019-09-09", "成都"),
]

# 京东集团公开年度业绩（来源：2025 年第四季度及全年业绩公告报道）
# 金额单位：亿元；同比增速单位：%
COMPANY_PROFILE = [
    (
        1,
        "京东集团",
        2025,
        13091.0,
        13.0,
        196.0,
        -52.66,
        2171.46,
        18.76,
        492.82,
        "https://finance.eastmoney.com/a/202603063663725071.html",
        "2026-03-05",
    ),
]

# 品类 -> 负责事业部，用于把订单归属到真实存在的事业部
CATEGORY_DEPARTMENT = {
    "手机通讯": 1,
    "数码配件": 1,
    "电脑办公": 2,
    "家用电器": 3,
    "食品饮料": 4,
    "家居日用": 4,
    "美妆个护": 5,
    "服饰鞋包": 5,
    "母婴玩具": 6,
    "运动户外": 6,
}

# ---------------------------------------------------------------------------
# 商品目录
# 字段：名称、品类、品牌、参考价、成本率、热度权重
# ---------------------------------------------------------------------------

PRODUCTS = [
    ("iPhone 16 128GB", "手机通讯", "苹果", 5399.00, 0.82, 10),
    ("iPhone 16 Pro 256GB", "手机通讯", "苹果", 8999.00, 0.82, 5),
    ("华为 Mate 70 12+256GB", "手机通讯", "华为", 5499.00, 0.78, 7),
    ("小米 15 12+256GB", "手机通讯", "小米", 4299.00, 0.75, 9),
    ("OPPO Find X8 12+256GB", "手机通讯", "OPPO", 4199.00, 0.74, 5),
    ("vivo X200 12+256GB", "手机通讯", "vivo", 4299.00, 0.74, 5),
    ("联想拯救者 Y9000P 2026", "电脑办公", "联想", 10499.00, 0.84, 4),
    ("MacBook Air 13 M4", "电脑办公", "苹果", 7999.00, 0.82, 3),
    ("华为 MateBook 14 2026", "电脑办公", "华为", 5999.00, 0.78, 4),
    ("戴尔 灵越 14 Plus", "电脑办公", "戴尔", 5299.00, 0.76, 3),
    ("罗技 MX Master 3S 鼠标", "电脑办公", "罗技", 699.00, 0.62, 7),
    ("海尔 460L 十字对开门冰箱", "家用电器", "海尔", 4299.00, 0.75, 6),
    ("美的 1.5匹 新一级变频空调", "家用电器", "美的", 2699.00, 0.72, 8),
    ("格力 云佳 1.5匹 空调", "家用电器", "格力", 2999.00, 0.72, 7),
    ("小米电视 S Pro 65英寸", "家用电器", "小米", 3499.00, 0.76, 6),
    ("戴森 V12 Detect Slim 吸尘器", "家用电器", "戴森", 3990.00, 0.68, 4),
    ("九阳 破壁机 Y88", "家用电器", "九阳", 599.00, 0.65, 6),
    ("索尼 WH-1000XM5 头戴耳机", "数码配件", "索尼", 2399.00, 0.72, 5),
    ("AirPods Pro 2", "数码配件", "苹果", 1899.00, 0.75, 7),
    ("大疆 Mini 4K 无人机", "数码配件", "大疆", 1799.00, 0.75, 4),
    ("任天堂 Switch OLED", "数码配件", "任天堂", 2099.00, 0.80, 4),
    ("小米 充电宝 20000mAh", "数码配件", "小米", 149.00, 0.65, 10),
    ("维达 抽纸 3层100抽24包", "家居日用", "维达", 59.90, 0.62, 10),
    ("蓝月亮 洗衣液 3kg", "家居日用", "蓝月亮", 49.90, 0.60, 10),
    ("苏泊尔 不粘炒锅 30cm", "家居日用", "苏泊尔", 299.00, 0.62, 7),
    ("富安娜 全棉四件套 1.8m", "家居日用", "富安娜", 399.00, 0.58, 6),
    ("茅台 飞天 53度 500ml", "食品饮料", "茅台", 1699.00, 0.80, 6),
    ("五粮液 第八代 52度 500ml", "食品饮料", "五粮液", 1049.00, 0.78, 5),
    ("三只松鼠 坚果大礼包", "食品饮料", "三只松鼠", 129.00, 0.62, 9),
    ("农夫山泉 550ml*24瓶", "食品饮料", "农夫山泉", 39.90, 0.58, 10),
    ("蒙牛 特仑苏 250ml*12盒", "食品饮料", "蒙牛", 69.90, 0.62, 10),
    ("兰蔻 小黑瓶精华 50ml", "美妆个护", "兰蔻", 1080.00, 0.72, 5),
    ("欧莱雅 紫熨斗眼霜 30ml", "美妆个护", "欧莱雅", 329.00, 0.65, 7),
    ("飞利浦 声波电动牙刷", "美妆个护", "飞利浦", 399.00, 0.62, 7),
    ("海蓝之谜 修护精萃水 150ml", "美妆个护", "海蓝之谜", 1100.00, 0.70, 3),
    ("优衣库 摇粒绒外套", "服饰鞋包", "优衣库", 199.00, 0.55, 8),
    ("安踏 氢跑鞋 5代", "服饰鞋包", "安踏", 399.00, 0.55, 7),
    ("李宁 运动卫衣", "服饰鞋包", "李宁", 299.00, 0.55, 6),
    ("波司登 轻薄羽绒服", "服饰鞋包", "波司登", 1299.00, 0.60, 5),
    ("帮宝适 一级帮纸尿裤 L码", "母婴玩具", "帮宝适", 159.00, 0.65, 8),
    ("爱他美 卓萃3段 800g", "母婴玩具", "爱他美", 328.00, 0.72, 6),
    ("乐高 城市系列 60409", "母婴玩具", "乐高", 599.00, 0.68, 4),
    ("迪卡侬 羽毛球拍 BR900", "运动户外", "迪卡侬", 199.00, 0.60, 6),
    ("骆驼 三合一冲锋衣", "运动户外", "骆驼", 499.00, 0.58, 5),
    ("Keep 瑜伽垫 加厚", "运动户外", "Keep", 129.00, 0.55, 6),
]

# ---------------------------------------------------------------------------
# 客户
# 城市权重按一线 / 新一线消费能力设置，保证“城市分布”分析有业务含义
# ---------------------------------------------------------------------------

CITY_QUOTAS = {
    "北京": 12,
    "上海": 11,
    "广州": 8,
    "深圳": 7,
    "成都": 5,
    "杭州": 5,
    "武汉": 4,
    "南京": 3,
    "西安": 3,
    "苏州": 2,
}

TOTAL_CUSTOMERS = sum(CITY_QUOTAS.values())  # 60

SURNAMES = list("王李张刘陈杨黄赵吴周徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾萧田董潘袁蔡蒋余于杜叶程魏苏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤")
GIVEN_NAMES = [
    "伟", "芳", "娜", "秀英", "敏", "静", "丽", "强", "磊", "洋",
    "艳", "勇", "军", "杰", "娟", "涛", "明", "超", "秀兰", "霞",
    "平", "刚", "桂英", "鹏", "华", "红", "玉兰", "飞", "鑫", "雪",
    "浩", "宇", "晨", "欣", "悦", "博", "文", "昊", "琳", "佳",
]

CUSTOMER_LEVELS = [
    ("普通会员", 52),
    ("银牌会员", 26),
    ("金牌会员", 16),
    ("钻石会员", 6),
]

CHANNELS = [
    ("京东APP", 58),
    ("京东小程序", 20),
    ("京东PC", 12),
    ("京东到家", 6),
    ("企业采购", 4),
]

ORDER_STATUS = ["已完成", "已发货", "待付款", "已取消", "退款中"]

# 不同月份的订单量权重：6 月 618、9 月开学季、10 月大促预热
MONTH_WEIGHTS = {
    1: 1.00, 2: 0.72, 3: 0.90, 4: 0.95, 5: 1.05,
    6: 1.55, 7: 0.85, 8: 1.00, 9: 1.15, 10: 1.25,
}

TOTAL_ORDERS = 460


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _weighted_choice(rng: random.Random, items: list[tuple[str, int]]) -> str:
    total = sum(weight for _, weight in items)
    point = rng.uniform(0, total)
    upto = 0.0
    for value, weight in items:
        upto += weight
        if point <= upto:
            return value
    return items[-1][0]


def _unique_names(rng: random.Random, count: int) -> list[str]:
    names: set[str] = set()
    result: list[str] = []
    while len(result) < count:
        name = rng.choice(SURNAMES) + rng.choice(GIVEN_NAMES)
        if name not in names:
            names.add(name)
            result.append(name)
    return result


def _build_customers(rng: random.Random):
    names = _unique_names(rng, TOTAL_CUSTOMERS)
    cities = [
        city
        for city, quota in CITY_QUOTAS.items()
        for _ in range(quota)
    ]
    rng.shuffle(cities)

    rows = []
    for index, (name, city) in enumerate(zip(names, cities), start=1):
        join_days = rng.randint(0, 900)
        join_date = date(2024, 1, 1) + timedelta(days=join_days)
        level = _weighted_choice(rng, CUSTOMER_LEVELS)
        rows.append(
            (
                index,
                name,
                city,
                rng.randint(22, 58),
                level,
                join_date.isoformat(),
                f"138****{rng.randint(1000, 9999)}",
            )
        )
    return rows


def _build_products():
    rows = []
    for index, (name, category, brand, price, cost_ratio, _weight) in enumerate(
        PRODUCTS, start=1
    ):
        rows.append(
            (
                index,
                name,
                category,
                brand,
                round(price, 2),
                round(price * cost_ratio, 2),
                rng_stock(index),
                "在售",
            )
        )
    return rows


def rng_stock(product_id: int) -> int:
    """库存只用于展示，固定公式保证每次重建一致。"""
    return 40 + (product_id * 37) % 460


def _build_orders(rng: random.Random):
    """返回 (orders, order_items)。"""
    total_weight = sum(MONTH_WEIGHTS.values())
    month_counts = {
        month: max(1, round(TOTAL_ORDERS * weight / total_weight))
        for month, weight in MONTH_WEIGHTS.items()
    }

    # 商品热度权重
    product_weights = [
        (product_id, PRODUCTS[product_id - 1][5])
        for product_id in range(1, len(PRODUCTS) + 1)
    ]
    product_dept = {
        product_id: CATEGORY_DEPARTMENT[PRODUCTS[product_id - 1][1]]
        for product_id in range(1, len(PRODUCTS) + 1)
    }

    employees_by_dept: dict[int, list[int]] = {}
    for employee_id, _name, dept_id, _position, _hire, _city in EMPLOYEES:
        employees_by_dept.setdefault(dept_id, []).append(employee_id)

    orders = []
    items = []
    item_id = 1
    order_id = 1
    today = date(2026, 10, 19)

    for month in sorted(month_counts):
        for _ in range(month_counts[month]):
            if month == DATA_END.month:
                day = rng.randint(1, DATA_END.day)
            else:
                last_day = (
                    date(2026, month + 1, 1) - timedelta(days=1)
                ).day
                day = rng.randint(1, last_day)

            order_date = date(2026, month, day)
            customer_id = rng.randint(1, TOTAL_CUSTOMERS)

            category_count = rng.choices(
                [1, 2, 3, 4], weights=[46, 32, 16, 6], k=1
            )[0]
            chosen: list[int] = []
            while len(chosen) < category_count:
                pid = int(_weighted_choice(rng, product_weights))
                if pid not in chosen:
                    chosen.append(pid)

            line_rows = []
            total_amount = 0.0
            for pid in chosen:
                list_price = PRODUCTS[pid - 1][3]
                quantity = (
                    rng.randint(1, 3)
                    if list_price < 500
                    else rng.randint(1, 2)
                    if list_price < 3000
                    else 1
                )
                discount = rng.uniform(0.88, 1.0)
                unit_price = round(list_price * discount, 2)
                amount = round(unit_price * quantity, 2)
                total_amount += amount
                line_rows.append(
                    (order_id, pid, quantity, unit_price, amount)
                )

            total_amount = round(total_amount, 2)
            dept_id = product_dept[chosen[0]]
            employee_id = rng.choice(employees_by_dept[dept_id])
            status = _order_status(rng, order_date, today)
            channel = _weighted_choice(rng, CHANNELS)
            order_no = (
                f"JD{order_date.strftime('%Y%m%d')}"
                f"{order_id:06d}"
            )
            created_at = datetime.combine(
                order_date,
                datetime.min.time(),
            ) + timedelta(
                hours=rng.randint(9, 22),
                minutes=rng.randint(0, 59),
                seconds=rng.randint(0, 59),
            )

            orders.append(
                (
                    order_id,
                    order_no,
                    customer_id,
                    employee_id,
                    order_date.isoformat(),
                    status,
                    channel,
                    total_amount,
                    created_at.strftime("%Y-%m-%d %H:%M:%S"),
                )
            )

            for line in line_rows:
                items.append((item_id, *line))
                item_id += 1

            order_id += 1

    return orders, items


def _order_status(rng: random.Random, order_date: date, today: date) -> str:
    age = (today - order_date).days
    if age >= 45:
        weights = [("已完成", 90), ("已取消", 5), ("退款中", 5)]
    elif age >= 15:
        weights = [("已完成", 70), ("已发货", 20), ("退款中", 5), ("已取消", 5)]
    elif age >= 5:
        weights = [
            ("已完成", 35), ("已发货", 45), ("退款中", 8),
            ("已取消", 7), ("待付款", 5),
        ]
    elif age >= 2:
        weights = [
            ("已发货", 50), ("待付款", 20), ("已完成", 15),
            ("退款中", 8), ("已取消", 7),
        ]
    else:
        weights = [
            ("待付款", 45), ("已发货", 35), ("已取消", 10),
            ("已完成", 5), ("退款中", 5),
        ]
    return _weighted_choice(rng, weights)


def _build_tickets(rng: random.Random):
    """工单数据：围绕企业内部 IT / 行政 / 财务服务场景。"""
    now = datetime(2026, 10, 19, 9, 30, 0)
    rows = [
        # user_id, issue, category, priority, status, assignee, resolution, hours_ago
        ("default_user", "内网账号无法登录，提示密码错误", "账号权限", "高", "已解决", "IT服务台-王工", "已重置域账号密码并完成登录验证", 36),
        ("default_user", "办公电脑开机蓝屏，无法进入系统", "办公设备", "高", "处理中", "IT服务台-李工", None, 20),
        ("default_user", "VPN 连接失败，外网无法访问内网系统", "网络服务", "中", "待处理", None, None, 6),
        ("default_user", "报销单提交后状态一直显示待审批", "财务报销", "中", "已解决", "财务共享中心-周会计", "已核实并推送审批流，报销单已进入打款流程", 72),
        ("default_user", "工牌丢失，需要补办门禁卡", "门禁工牌", "低", "待处理", None, None, 12),
        ("user_001", "京东ME无法接收消息通知", "软件系统", "中", "处理中", "IT服务台-赵工", None, 28),
        ("user_001", "会议室投屏设备无法识别笔记本", "办公设备", "低", "已解决", "行政支持-陈老师", "更换 HDMI 转接器后恢复", 50),
        ("user_001", "希望申请正版办公软件授权", "软件系统", "中", "待处理", None, None, 3),
        ("user_002", "打印机卡纸且提示缺墨", "办公设备", "低", "已解决", "行政支持-陈老师", "已清理卡纸并更换硒鼓", 96),
        ("user_002", "食堂餐补余额未到账", "行政服务", "中", "处理中", "行政支持-刘老师", None, 18),
        ("user_002", "出差机票预订系统无法选择航班", "差旅服务", "高", "已解决", "差旅平台-运维", "已恢复航班数据同步", 120),
        ("user_003", "新员工入职账号开通延迟", "账号权限", "中", "已解决", "IT服务台-王工", "已补开账号并同步至各业务系统", 64),
        ("user_003", "企业微信文件传输失败", "网络服务", "中", "已关闭", "IT服务台-李工", "用户已改用内网网盘，问题关闭", 150),
        ("user_004", "申请更换笔记本电脑电池", "办公设备", "低", "待处理", None, None, 8),
        ("user_004", "年假余额查询结果与系统不一致", "人力资源", "中", "处理中", "HR共享中心-何老师", None, 14),
        ("user_005", "门禁卡消磁，无法进入办公区", "门禁工牌", "高", "已解决", "行政支持-陈老师", "已更换新卡并重新授权", 40),
        ("user_005", "京东内部知识库搜索不到制度文件", "软件系统", "低", "已解决", "知识运营-孙老师", "已补充索引并验证搜索命中", 88),
        ("user_006", "发票抬头信息填写错误需要修改", "财务报销", "中", "已关闭", "财务共享中心-周会计", "用户自行作废后重新提交", 200),
    ]

    tickets = []
    for index, (
        user_id, issue, category, priority, status, assignee, resolution, hours_ago
    ) in enumerate(rows, start=1):
        created = now - timedelta(hours=hours_ago)
        updated = created + timedelta(hours=rng.randint(1, min(hours_ago, 24)))
        tickets.append(
            (
                user_id,
                issue,
                category,
                priority,
                status,
                assignee,
                resolution,
                created.strftime("%Y-%m-%d %H:%M:%S"),
                updated.strftime("%Y-%m-%d %H:%M:%S"),
            )
        )
    return tickets


# ---------------------------------------------------------------------------
# 建库
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT,
    manager TEXT,
    created_at TEXT DEFAULT '2024-01-01'
);

CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    position TEXT,
    hire_date TEXT,
    city TEXT,
    status TEXT DEFAULT '在职'
);

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT,
    age INTEGER,
    level TEXT,
    join_date TEXT,
    phone TEXT
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    brand TEXT,
    unit_price REAL NOT NULL,
    cost REAL,
    stock INTEGER,
    status TEXT DEFAULT '在售'
);

CREATE TABLE company_profile (
    id INTEGER PRIMARY KEY,
    company TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    revenue REAL,
    revenue_yoy REAL,
    net_profit REAL,
    net_profit_yoy REAL,
    logistics_revenue REAL,
    logistics_yoy REAL,
    new_business_revenue REAL,
    source TEXT,
    updated_at TEXT
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    order_no TEXT UNIQUE NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    employee_id INTEGER REFERENCES employees(id),
    order_date TEXT NOT NULL,
    status TEXT NOT NULL,
    channel TEXT,
    total_amount REAL NOT NULL,
    created_at TEXT
);

CREATE TABLE order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    amount REAL NOT NULL
);

CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_items_order ON order_items(order_id);
CREATE INDEX idx_items_product ON order_items(product_id);
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_employees_department ON employees(department_id);
"""

VIEWS_SQL = """
CREATE VIEW v_sales_line AS
SELECT
    o.id            AS order_id,
    o.order_no      AS order_no,
    o.order_date    AS order_date,
    substr(o.order_date, 1, 7) AS order_month,
    o.status        AS status,
    o.channel       AS channel,
    c.id            AS customer_id,
    c.name          AS customer_name,
    c.city          AS customer_city,
    c.level         AS customer_level,
    e.id            AS employee_id,
    e.name          AS sales_rep,
    d.id            AS department_id,
    d.name          AS department,
    p.id            AS product_id,
    p.name          AS product_name,
    p.category      AS category,
    p.brand         AS brand,
    p.cost          AS unit_cost,
    oi.quantity     AS quantity,
    oi.unit_price   AS unit_price,
    oi.amount       AS amount
FROM orders o
JOIN customers c ON c.id = o.customer_id
LEFT JOIN employees e ON e.id = o.employee_id
LEFT JOIN departments d ON d.id = e.department_id
JOIN order_items oi ON oi.order_id = o.id
JOIN products p ON p.id = oi.product_id;

CREATE VIEW v_order_summary AS
SELECT
    o.id            AS order_id,
    o.order_no      AS order_no,
    o.order_date    AS order_date,
    substr(o.order_date, 1, 7) AS order_month,
    o.status        AS status,
    o.channel       AS channel,
    c.name          AS customer_name,
    c.city          AS customer_city,
    e.name          AS sales_rep,
    d.name          AS department,
    COUNT(oi.id)    AS item_count,
    SUM(oi.quantity) AS total_quantity,
    o.total_amount  AS total_amount
FROM orders o
JOIN customers c ON c.id = o.customer_id
LEFT JOIN employees e ON e.id = o.employee_id
LEFT JOIN departments d ON d.id = e.department_id
JOIN order_items oi ON oi.order_id = o.id
GROUP BY o.id;
"""

TICKET_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    issue TEXT NOT NULL,
    category TEXT DEFAULT '其他',
    priority TEXT DEFAULT '中',
    status TEXT DEFAULT '待处理',
    assignee TEXT,
    resolution TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
"""


def seed_business_db(db_path: Path = DB_PATH) -> None:
    rng = random.Random(RANDOM_SEED)

    customers = _build_customers(rng)
    products = _build_products()
    orders, order_items = _build_orders(rng)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF")

        # 先删视图，再删表，避免 DROP TABLE 命中视图时报错
        for view in ("v_sales_line", "v_order_summary"):
            cursor.execute(f"DROP VIEW IF EXISTS {view}")

        for table in (
            "order_items",
            "orders",
            "products",
            "company_profile",
            "customers",
            "employees",
            "departments",
        ):
            cursor.execute(f"DROP TABLE IF EXISTS {table}")

        cursor.executescript(SCHEMA_SQL)
        cursor.executescript(VIEWS_SQL)

        cursor.executemany(
            "INSERT INTO departments VALUES (?,?,?,?,?)",
            [(i, name, city, manager, "2024-01-01") for i, name, city, manager in DEPARTMENTS],
        )
        cursor.executemany(
            "INSERT INTO employees VALUES (?,?,?,?,?,?,?)",
            [(i, name, dept, pos, hire, city, "在职") for i, name, dept, pos, hire, city in EMPLOYEES],
        )
        cursor.executemany(
            "INSERT INTO customers VALUES (?,?,?,?,?,?,?)",
            customers,
        )
        cursor.executemany(
            "INSERT INTO products VALUES (?,?,?,?,?,?,?,?)",
            products,
        )
        cursor.executemany(
            "INSERT INTO company_profile VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            COMPANY_PROFILE,
        )
        cursor.executemany(
            "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)",
            orders,
        )
        cursor.executemany(
            "INSERT INTO order_items VALUES (?,?,?,?,?,?)",
            order_items,
        )

        conn.commit()
    finally:
        conn.close()

    print(
        f"[seed] business.db 已生成：{len(DEPARTMENTS)} 个部门、"
        f"{len(EMPLOYEES)} 名员工、{len(customers)} 位客户、"
        f"{len(products)} 个商品、{len(orders)} 笔订单、"
        f"{len(order_items)} 条订单明细、"
        f"{len(COMPANY_PROFILE)} 条集团公开业绩"
    )


def seed_ticket_db(db_path: Path = BASE_DIR / "tickets.db") -> None:
    rng = random.Random(RANDOM_SEED + 1)
    tickets = _build_tickets(rng)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS tickets")
        cursor.executescript(TICKET_SCHEMA_SQL)
        cursor.executemany(
            """
            INSERT INTO tickets
                (user_id, issue, category, priority, status,
                 assignee, resolution, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            tickets,
        )
        conn.commit()
    finally:
        conn.close()

    print(f"[seed] tickets.db 已生成：{len(tickets)} 张工单")


def main() -> None:
    seed_business_db()
    seed_ticket_db()


if __name__ == "__main__":
    main()
