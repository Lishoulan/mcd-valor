# -*- coding: utf-8 -*-
"""把 MCP 返回的 Markdown / CSV 文本解析成结构化数据。

每个函数都只依赖标准库，且对字段缺失做了防御性处理——
服务端文案随时会改，宁可少解析一个字段也不要整条命令崩掉。
"""

import re
from datetime import date, datetime

DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def parse_date(text):
    """从任意文本里抓第一个 yyyy-MM-dd，失败返回 None。"""
    if not text:
        return None
    m = DATE_RE.search(str(text))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def days_left(end_date, today=None):
    """距离到期还有几天。负数=已过期。"""
    if end_date is None:
        return None
    today = today or date.today()
    return (end_date - today).days


# ---------------------------------------------------------------- 券


def parse_coupons(text):
    """解析 query-my-coupons 的 Markdown。

    实测格式：
        ## 9.9元中杯冰美式
        - **优惠**: ¥9.9 (用券价格)
        - **有效期**: 2026-10-06 00:00-2026-10-12 23:59
        - **领取时间**: 4日前收到
        - **标签**: 到店专用、外送专用
    """
    coupons = []
    if not text:
        return coupons
    if "暂无可用优惠券" in text:
        return coupons

    total = None
    m = re.search(r"共\s*(\d+)\s*张", text)
    if m:
        total = int(m.group(1))

    # 以 "## 券名" 切块（### 是图片/其它层级，不影响）
    blocks = re.split(r"^##\s+", text, flags=re.M)[1:]
    for block in blocks:
        lines = block.splitlines()
        name = lines[0].strip()
        if not name:
            continue
        item = {"name": name, "price": "", "start": None, "end": None,
                "end_raw": "", "got": "", "tags": []}

        m = re.search(r"\*\*优惠\*\*[:：]\s*(.+)", block)
        if m:
            item["price"] = m.group(1).strip()
        m = re.search(r"\*\*有效期\*\*[:：]\s*(.+)", block)
        if m:
            period = m.group(1).strip()
            item["end_raw"] = period
            # 注意：findall 带分组时返回元组，必须取 group(0)拿完整日期串
            dates = [dm.group(0) for dm in DATE_RE.finditer(period)]
            if dates:
                item["start"] = parse_date(dates[0])
                item["end"] = parse_date(dates[1] if len(dates) > 1 else dates[0])
        m = re.search(r"\*\*领取时间\*\*[:：]\s*(.+)", block)
        if m:
            item["got"] = m.group(1).strip()
        m = re.search(r"\*\*标签\*\*[:：]\s*(.+)", block)
        if m:
            item["tags"] = [t.strip() for t in re.split(r"[、,，/]", m.group(1)) if t.strip()]

        # 有些券名里带 markdown 残留
        item["name"] = re.sub(r"\s*!\[.*?\]\(.*?\)", "", item["name"]).strip()
        coupons.append(item)
    return coupons, total


# ---------------------------------------------------------------- 营养数据


def parse_nutrition(data):
    """解析 list-nutrition-foods 的 data 字段。

    实测格式：
        [160]{productName,nutritionDescription,energyKj,energyKcal,protein,
               fat,carbohydrate,sodium,calcium}:
          猪柳麦满分,null,1288,308,16,16,24,781,213
          ...
    """
    foods = []
    if not data:
        return foods
    text = data if isinstance(data, str) else json_dumps(data)
    if ":" not in text:
        return foods
    body = text.split(":", 1)[1]
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("[") or line.startswith("{"):
            continue
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < 4:
            continue
        name = cols[0]
        if not name or name in ("null", "None"):
            continue

        def num(idx):
            try:
                return float(cols[idx])
            except (ValueError, IndexError):
                return 0.0

        foods.append({
            "name": name,
            "desc": cols[1] if len(cols) > 1 and cols[1] not in ("null", "None") else "",
            "kj": num(2),
            "kcal": num(3),
            "protein": num(4),
            "fat": num(5),
            "carb": num(6),
            "sodium": num(7),
            "calcium": num(8) if len(cols) > 8 else 0.0,
        })
    return foods


def json_dumps(obj):
    import json
    return json.dumps(obj, ensure_ascii=False)


# ---------------------------------------------------------------- 活动日历


def parse_calendar(text):
    """解析 campaign-calendar 的 Markdown。

    实测格式：
        #### 2026年10月10日 今日
        -   **活动标题**：xxx
            **活动内容介绍**：xxx
        #### 2026年10月11日          <- 未来日期无后缀
    """
    days = []
    if not text:
        return days
    pattern = re.compile(r"^#{3,4}\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(.*)$", re.M)
    marks = list(pattern.finditer(text))
    for i, mk in enumerate(marks):
        start = mk.end()
        seg = text[start: marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        label = mk.group(4).strip()
        try:
            d = date(int(mk.group(1)), int(mk.group(2)), int(mk.group(3)))
        except ValueError:
            continue
        titles = re.findall(r"\*\*活动标题\*\*[:：]\s*(.+)", seg)
        intros = re.findall(r"\*\*活动内容介绍\*\*[:：]\s*(.+)", seg)
        days.append({
            "date": d,
            "label": label,
            "status": ("today" if "今日" in label else
                       "past" if "往期" in label else "future"),
            "activities": [t.strip() for t in titles if t.strip()],
            "intros": [i.strip() for i in intros if i.strip()],
        })
    return days


# ---------------------------------------------------------------- 可领券


def parse_available(text):
    """解析 available-coupons 的 Markdown：
        - 优惠券标题：xxx \\
          状态：已领取 \\
    """
    items = []
    if not text:
        return items
    for m in re.finditer(r"-\s*优惠券标题[:：]\s*(.+?)\s*\\?\s*\n\s*状态[:：]\s*(.+?)\s*\\?\s*$",
                         text, flags=re.M):
        items.append({"name": m.group(1).strip(), "status": m.group(2).strip()})
    if items:
        return items
    # 退化：逐行扫描
    cur = None
    for line in text.splitlines():
        t = line.strip().rstrip("\\").strip()
        if t.startswith("优惠券标题"):
            cur = {"name": re.sub(r"^[-]?\s*优惠券标题[:：]\s*", "", t), "status": ""}
            items.append(cur)
        elif t.startswith("状态") and cur is not None:
            cur["status"] = re.sub(r"^状态[:：]\s*", "", t)
    return items


# ---------------------------------------------------------------- 订单


def parse_orders(payload):
    """从 order-list 的 JSON 里取订单数组。"""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("list", "records", "orders"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def order_items(order):
    """把订单展开成 [(商品名, 数量)]，含套餐子项。"""
    items = []
    for prod in order.get("orderProductList") or []:
        qty = prod.get("quantity") or 1
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            qty = 1
        items.append((prod.get("productName") or "未知商品", qty))
        for sub in prod.get("comboItemList") or []:
            sqty = sub.get("quantity") or 1
            try:
                sqty = int(sqty)
            except (TypeError, ValueError):
                sqty = 1
            items.append((sub.get("name") or sub.get("productName") or "套餐子项", sqty))
    return items


def to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
