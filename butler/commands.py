# -*- coding: utf-8 -*-
"""积值Valor · 11 个子命令的实现。"""

from collections import Counter, defaultdict
from datetime import date, timedelta

import re

from . import parsers as P
from . import ui as U

MCD = "\U0001F354"  # 🍔


# ================================================================ 工具函数


def _expiry_color(days):
    """按剩余天数上色：已过期 <0 灰、0 黄红、<=2 红、<=5 黄、其余绿。"""
    if days is None:
        return U.grey("未知"), ""
    if days < 0:
        return U.grey("已过期"), U.grey("✗")
    if days == 0:
        return U.yellow(U.bold("今天到期")), U.bold("\U0001F525")
    if days <= 2:
        return U.red("%d 天后到期" % days), U.red("\U0001F525")
    if days <= 5:
        return U.yellow("%d 天后到期" % days), U.yellow("!")
    return U.green("%d 天后到期" % days), U.green("·")


def _kcal_color(kcal):
    if kcal >= 500:
        return U.red
    if kcal >= 300:
        return U.yellow
    return U.green


def fetch_account(client):
    payload = client.call_json("query-my-account")
    return (payload.get("data") or {})


def fetch_all_coupons(client, max_pages=5, page_size=200):
    """翻页拉全部券（服务端上限 5 页 x200 条）。"""
    all_coupons, total = [], None
    for page in range(1, max_pages + 1):
        text = client.call_text("query-my-coupons", {"page": str(page), "pageSize": str(page_size)})
        coupons, page_total = P.parse_coupons(text)
        if total is None:
            total = page_total
        if not coupons:
            break
        all_coupons.extend(coupons)
        if len(coupons) < page_size:
            break
    return all_coupons, total


# ================================================================ 1. account


def cmd_account(client, args):
    U.out(U.title("%s 积值 · 积分账户总览" % MCD))
    data = fetch_account(client)

    available = P.to_float(data.get("availablePoint"))
    accumulative = P.to_float(data.get("accumulativePoint"))
    used = P.to_float(data.get("usedPoint"))
    expired = P.to_float(data.get("expiredPoint"))
    cur_exp = P.to_float(data.get("currentMouthExpirePoint"))
    nxt_exp = P.to_float(data.get("nextMouthExpirePoint"))
    last_exp = P.to_float(data.get("lastMouthExpirePoint"))
    frozen = P.to_float(data.get("frozenPoint"))

    U.out(U.kv("账户 ID", U.grey((data.get("accountId") or "-")[:8] + "…")))
    U.out(U.kv("货币类型", data.get("currency") or "麦享会积分"))
    U.out()
    U.out(U.kv("可用积分", U.bold("%s 分" % _num(available)), color=U.green))
    U.out(U.kv("累计积分", "%s 分" % _num(accumulative)))
    U.out(U.kv("已使用积分", "%s 分" % _num(used)))
    if frozen:
        U.out(U.kv("冻结积分", U.yellow("%s 分" % _num(frozen))))
    U.out()
    U.out(U.kv("本月将过期", ("%s 分" % _num(cur_exp)) if cur_exp else U.grey("0 分（本月无积分过期）")))
    U.out(U.kv("下月将过期", "%s 分" % _num(nxt_exp)))
    U.out(U.kv("上月已过期", "%s 分" % _num(last_exp)))

    U.out()
    if expired > 0:
        U.out("  " + U.red(U.bold("⚠  你已经白白过期了 %s 分" % _num(expired))))
        U.out("  " + U.grey("这些积分本来可以换的。下一张券包别再让它躺着过期了。"))
    else:
        U.out("  " + U.green("✓ 历史零过期，你把积分守得很好。"))

    if cur_exp > 0:
        U.out("  " + U.yellow("⏰ 本月还有 %s 分要过期，去看看能换什么：`python -m butler expiring`" % _num(cur_exp)))
    U.out()
    return 0


# ================================================================ 2. coupons


def cmd_coupons(client, args):
    U.out(U.title("%s 积值 · 我的券包" % MCD))
    coupons, total = fetch_all_coupons(client)
    today = date.today()

    if not coupons:
        U.out(U.yellow("  你的卡包是空的 —— 一张券都没有。"))
        U.out(U.grey("  去 `python -m butler claim` 一键把能领的全领了。"))
        U.out()
        return 0

    total = total if total is not None else len(coupons)
    U.out(U.grey("  共 %d 张券（服务端统计 %d 张）· 今天 %s" % (len(coupons), total, today)))
    U.out()

    rows, soon = [], []
    for c in sorted(coupons, key=lambda x: (x["end"] or date.max)):
        d = P.days_left(c["end"], today)
        color, icon = _expiry_color(d)
        rows.append([
            c["name"],
            _price(c["price"]) or "-",
            (c["end"].isoformat() if c["end"] else "?"),
            color + (" " + icon if icon else ""),
            U.grey("/".join(c["tags"])) if c["tags"] else U.grey("-"),
        ])
        if d is not None and 0 <= d <= 3:
            soon.append((d, c))

    headers = ["券名", "优惠", "有效期至", "剩余", "适用"]
    aligns = ["l", "r", "l", "l", "l"]
    U.out(U.table(headers, rows, aligns))
    U.out()

    if soon:
        U.out(U.bold("  ⏳ 3 天内到期的券（%d 张）—— 别浪费：" % len(soon)))
        for d, c in sorted(soon, key=lambda x: x[0]):
            color, icon = _expiry_color(d)
            U.out("    %s %s%s" % (color, c["name"], U.grey("  " + _price(c["price"]))))
        U.out()
    else:
        U.out(U.green("  ✓ 3 天内没有券要过期，慢慢吃。"))
        U.out()

    expired = [c for c in coupons if (P.days_left(c["end"], today) or 1) < 0]
    if expired:
        U.out(U.grey("  另有 %d 张已过期券躺在卡包里，可手动清理。" % len(expired)))
        U.out()
    return 0


def _w(text):
    return U._w(text)


def _price(text):
    """把 '¥15 (用券价格)' 压成 '¥15'。"""
    if not text:
        return ""
    return text.split("(")[0].strip()


def _num(x):
    """整数不带小数点，带小数保留 1 位。"""
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return "%.1f" % x


# ================================================================ 3. claim


def cmd_claim(client, args):
    U.out(U.title("%s 积值 · 一键领券" % MCD))
    before = fetch_all_coupons(client)
    before_coupons, before_total = before
    U.out(U.grey("  领券前卡包：%d 张" % len(before_coupons)))

    text, payload = client.call_tool("auto-bind-coupons")
    U.out()

    # auto-bind-coupons 返回的是纯 Markdown，没有 JSON：
    #   成功 -> "### 领券成功..." / "### 领券失败\n\n错误信息：暂无可领取的优惠券"
    failed = ("领券失败" in text) or ("错误信息" in text)
    err = ""
    m = re.search(r"错误信息[:：]\s*(.+)", text)
    if m:
        err = m.group(1).strip()

    if payload:
        data = payload.get("data")
        U.out(U.kv("接口返回", U.grey(str(payload.get("message") or "ok"))))
        if isinstance(data, dict):
            for k in ("successCount", "bindCount", "total", "couponCount"):
                if k in data:
                    U.out(U.kv(k, data[k]))
        elif isinstance(data, list):
            U.out(U.kv("返回条目", len(data)))

    # 服务端成功文案里的张数（若有）
    claimed = None
    m = re.search(r"(\d+)\s*张", text)
    if m and "领券成功" in text:
        claimed = int(m.group(1))

    after_coupons, after_total = fetch_all_coupons(client)
    delta = len(after_coupons) - len(before_coupons)
    total_now = after_total if after_total is not None else len(after_coupons)

    U.out()
    if failed:
        reason = err or "服务端未给出原因"
        if "暂无可领取" in reason or "无可领取" in reason:
            U.out(U.yellow("  ✓ 券都领完了 —— 当前没有新的可领优惠券。"))
        else:
            U.out(U.red("  ✗ 领券失败：%s" % reason))
        U.out(U.grey("  看看卡包现状：python -m butler coupons"))
    elif claimed is not None and claimed > 0:
        U.out(U.green(U.bold("  ✓ 领券成功，本次领取 %d 张（卡包现有 %d 张）" % (claimed, total_now))))
    elif delta > 0:
        U.out(U.green(U.bold("  ✓ 领券成功，卡包 +%d 张（现在共 %d 张）" % (delta, total_now))))
    elif delta == 0:
        U.out(U.yellow("  没有新券入账 —— 要么都已领取，要么活动还没上新。"))
    else:
        U.out(U.yellow("  卡包数量变化 %d（可能同时有券过期或被核销），跑一次 coupons 看明细。" % delta))

    new_soon = [c for c in after_coupons if 0 <= (P.days_left(c["end"]) or 99) <= 3]
    if delta > 0 and new_soon:
        U.out(U.yellow("  其中 %d 张 3 天内到期：python -m butler expiring" % len(new_soon)))
    U.out()
    return 0


# ================================================================ 4. expiring（卖点）


def cmd_expiring(client, args):
    horizon = args.window if args.window else 3
    today = date.today()
    U.out(U.title("%s 积值 · %d 天内什么要过期" % (MCD, horizon)))
    U.out(U.grey("  今天 %s · 数据来自 mcd-mcp 实时查询" % today))
    U.out()

    timeline = []  # (剩余天数, 类别, 名称, 详情)

    # --- 积分侧 ---
    try:
        acc = fetch_account(client)
    except Exception as exc:  # 积分查询失败不该拖垮整个命令
        acc = {}
        U.out(U.yellow("  ⚠ 积分账户查询失败：%s" % exc))
    cur_exp = P.to_float(acc.get("currentMouthExpirePoint"))
    if cur_exp > 0:
        month_end = _month_end(today)
        d = (month_end - today).days
        timeline.append((d, "积分", "%s 分积分" % _num(cur_exp),
                         "本月 %s 到期" % month_end))
    else:
        U.out(U.green("  ✓ 积分：本月无过期积分（可用 %s 分）"
                      % _num(P.to_float(acc.get("availablePoint")))))

    # --- 券侧 ---
    coupons, _ = fetch_all_coupons(client)
    for c in coupons:
        d = P.days_left(c["end"], today)
        if d is None or d > horizon:
            continue
        detail = c["end"].isoformat() + " 到期"
        if _price(c["price"]):
            detail += " · " + _price(c["price"])
        if c["tags"]:
            detail += " · " + "/".join(c["tags"])
        timeline.append((d, "券", c["name"], detail))
    U.out(U.grey("  ✓ 券包：共 %d 张，%d 天内到期 %d 张"
                 % (len(coupons), horizon, len([t for t in timeline if t[1] == "券"]))))
    U.out()

    if not timeline:
        U.out(U.green(U.bold("  🎉 %d 天内什么都不用过期 —— 钱包很健康。" % horizon)))
        U.out()
        return 0

    timeline.sort(key=lambda x: (x[0], x[1]))
    U.out(U.rule())
    U.out(U.bold("  倒计时清单"))
    U.out(U.rule())
    for d, kind, name, detail in timeline:
        if d < 0:
            badge = U.grey("已过期")
        elif d == 0:
            badge = U.bold(U.yellow("今天 "))
        else:
            badge = _expiry_color(d)[0]
        U.out("  %s %s %s" % (badge, U.bold(name), U.grey(detail)))
        # 进度条：越紧急越满（剩 0 天 = 满格）
        filled = horizon - max(0, min(d, horizon))
        bar = U.bar(max(1, filled), horizon, width=12)
        tint = U.red if (d is not None and d <= 2) else U.yellow
        U.out("       %s %s" % (tint(bar), U.grey("剩 %d 天 / 窗口 %d 天" % (max(0, d), horizon))))
    U.out(U.rule())
    U.out()

    # --- 行动建议 ---
    urgent = [t for t in timeline if t[0] is not None and 0 <= t[0] <= 2]
    if urgent:
        U.out(U.red(U.bold("  ⚠ %d 项已经进入最后 48 小时：" % len(urgent))))
        for d, kind, name, _ in urgent:
            when = "今天" if d == 0 else ("明天" if d == 1 else "后天")
            U.out("    · %s → %s之前用掉" % (U.bold(name), when))
    else:
        U.out(U.yellow("  ⏰ 最近一项在 %d 天后，安排这周用掉就行。" % timeline[0][0]))
    U.out(U.grey("  想顺手把到期积分换掉：`python -m butler account` 看余额"))
    U.out()
    return 0


def _month_end(d):
    return date(d.year + (d.month // 12), (d.month % 12) + 1, 1) - timedelta(days=1)


# ================================================================ 5. nutrition


def cmd_nutrition(client, args):
    U.out(U.title("%s 积值 · 餐品营养查询" % MCD))
    payload = client.call_json("list-nutrition-foods")
    foods = P.parse_nutrition((payload.get("data") or ""))
    if not foods:
        U.out(U.yellow("  没解析到营养数据。"))
        return 1

    kw = (args.keyword or "").strip()
    if kw:
        foods = [f for f in foods if kw in f["name"] or kw in (f["desc"] or "")]
        if not foods:
            U.out(U.yellow("  没有餐品名包含「%s」。换个关键词试试，或不带参数看全部 %d 条。" % (kw, len(P.parse_nutrition(payload.get("data") or "")))))
            return 1
        U.out(U.grey("  「%s」命中 %d 条，按热量升序：" % (kw, len(foods))))
    else:
        foods.sort(key=lambda f: f["kcal"])
        foods = foods[:25]
        U.out(U.grey("  全量 %d 条，按热量升序取前 25 条。带关键词可精确过滤。" % len(P.parse_nutrition(payload.get("data") or ""))))
    U.out()

    foods.sort(key=lambda f: f["kcal"])
    rows = []
    for f in foods:
        color = _kcal_color(f["kcal"])
        rows.append([
            f["name"],
            color(U.bold("%d" % round(f["kcal"]))),
            "%d" % round(f["kj"]),
            "%g" % f["protein"],
            "%g" % f["fat"],
            "%g" % f["carb"],
            "%d" % round(f["sodium"]),
            "%d" % round(f["calcium"]),
        ])
    U.out(U.table(
        ["餐品", "热量kcal", "能量kJ", "蛋白g", "脂肪g", "碳水g", "钠mg", "钙mg"],
        rows, ["l", "r", "r", "r", "r", "r", "r", "r"],
    ))
    U.out()
    U.out(U.grey("  图例：") + U.red("≥500kcal 高热量") + U.grey(" · ")
          + U.yellow("300-500kcal 中等") + U.grey(" · ")
          + U.green("<300kcal 清爽"))
    U.out()
    return 0


# ================================================================ 6. stores


def cmd_stores(client, args):
    U.out(U.title("%s 积值 · 附近门店" % MCD))
    be_type = 5 if getattr(args, "drive_through", False) else 1
    search_type = 2 if getattr(args, "city", None) else 1
    if search_type == 2 and not args.city:
        search_type = 1

    params = {"beType": be_type, "searchType": search_type}
    if args.keyword:
        params["keyword"] = args.keyword
    if search_type == 2:
        params["city"] = args.city

    U.out(U.grey("  查询条件：%s%s%s"
                 % ("得来速车道 " if be_type == 5 else "到店自提 ",
                    "按城市" if search_type == 2 else "收藏/默认",
                    (" · 关键词「%s」" % args.keyword) if args.keyword else "")))
    U.out()

    payload = client.call_json("query-nearby-stores", params)
    stores = payload.get("data") or []
    if isinstance(stores, dict):
        stores = stores.get("list") or stores.get("stores") or []

    total_fetched = len(stores)
    # 服务端在 searchType=1（收藏/默认）下会忽略 keyword，
    # 所以这里在本地再过滤一次，否则搜什么词都返回同一批店。
    if args.keyword and search_type == 1:
        kw = args.keyword.lower()
        stores = [s for s in stores
                  if kw in (s.get("storeName") or "").lower()
                  or kw in (s.get("address") or "").lower()]

    if not stores:
        if args.keyword and total_fetched:
            U.out(U.yellow("  搜到 %d 家默认/收藏门店，但都不含「%s」。" % (total_fetched, args.keyword)))
            U.out()
        else:
            U.out(U.yellow("  没有搜到门店。"))
            U.out()
        U.out("  可以试试：")
        U.out(U.grey("    · 换个关键词                python -m butler stores 火车站"))
        U.out(U.grey("    · 指定城市按地理位置搜      python -m butler stores 北大 --city 北京"))
        U.out(U.grey("    · 搜得来速车道取餐          python -m butler stores 地铁站 --dt"))
        U.out()
        U.out(U.grey("  说明：默认 searchType=1 搜的是收藏/默认门店，关键词在本地过滤；"))
        U.out(U.grey("  想让服务端按地理位置搜，请带 --city。"))
        U.out()
        return 0

    rows = []
    for s in stores:
        dist = s.get("distance")
        try:
            dist_txt = "%.1fkm" % float(dist) if float(dist) > 0 else "-"
        except (TypeError, ValueError):
            dist_txt = "-"
        resv = "可预约" if s.get("reservation") else U.grey("不可预约")
        rows.append([
            s.get("storeName") or "-",
            s.get("storeCode") or "-",
            dist_txt,
            resv,
            U.grey(U.truncate(s.get("address") or "-", 40)),
        ])
    U.out(U.table(["门店", "门店编号", "距离", "预约", "地址"], rows,
                  ["l", "l", "r", "l", "l"]))
    U.out()
    U.out(U.grey("  共 %d 家。门店编号可用于下单/查券类工具。" % len(stores)))
    U.out()
    return 0


# ================================================================ 7. calendar


def cmd_calendar(client, args):
    U.out(U.title("%s 积值 · 本月活动日历" % MCD))
    params = {}
    if getattr(args, "date", None):
        params["specifiedDate"] = args.date
    text = client.call_text("campaign-calendar", params)
    days = P.parse_calendar(text)
    if not days:
        U.out(U.yellow("  没解析到活动（服务端格式可能变了）。"))
        return 1

    today = date.today()
    # 有 specifiedDate 时只展示返回的三天
    if not params:
        days = [d for d in days if d["date"].month == today.month]

    U.out(U.grey("  共 %d 天有活动" % len(days)))
    U.out()
    for d in days:
        dd = P.days_left(d["date"], today)
        if d["status"] == "today":
            head = U.bold(U.brand("● %s 今日" % d["date"].strftime("%m-%d")))
        elif d["status"] == "past":
            head = U.grey("○ %s %s" % (d["date"].strftime("%m-%d"), d["label"]))
        else:
            head = U.cyan("○ %s  %s" % (d["date"].strftime("%m-%d"),
                                      ("%d 天后" % dd) if dd is not None else ""))
        U.out("  " + head)
        for i, title in enumerate(d["activities"]):
            U.out("      · " + U.bold(title))
            if i == 0 and d["intros"]:
                intro = d["intros"][0].replace("\n", " ")
                U.out("        " + U.grey(intro[:70]))
    U.out()
    U.out(U.grey("  查看指定日期前后活动：python -m butler calendar --date 2026-10-15"))
    U.out()
    return 0


# ================================================================ 8. spend


def cmd_spend(client, args):
    U.out(U.title("%s 积值 · 消费报告" % MCD))
    payload = client.call_json("order-list")
    orders = P.parse_orders(payload)
    if not orders:
        U.out(U.yellow("  没有查到历史订单（可能还没下过单，或仅含商城订单）。"))
        return 0

    total = sum(P.to_float(o.get("realTotalAmount")) for o in orders)
    paid = [o for o in orders if P.to_float(o.get("realTotalAmount")) > 0]
    paid_total = sum(P.to_float(o.get("realTotalAmount")) for o in paid)
    avg_all = total / len(orders)
    avg_paid = paid_total / len(paid) if paid else 0.0

    stores = Counter(o.get("storeName") or "未知门店" for o in orders)
    items = Counter()
    for o in orders:
        for name, qty in P.order_items(o):
            items[name] += qty

    times = sorted(P.parse_date((o.get("createTime") or "")[:10]) or date.min for o in orders)
    times = [t for t in times if t != date.min]

    U.out(U.kv("订单总数", U.bold("%d 单" % len(orders))))
    U.out(U.kv("总花费", U.bold(U.brand("¥%s" % _num(total))), color=U.brand))
    U.out(U.kv("实付订单", "%d 单（%d 单为 0 元：积分兑换/赠券）" % (len(paid), len(orders) - len(paid))))
    if times:
        U.out(U.kv("消费区间", "%s ~ %s" % (times[0].isoformat(), times[-1].isoformat())))
    U.out()
    U.out(U.kv("客单价（全部）", "¥%s" % _num(avg_all)))
    if paid:
        U.out(U.kv("客单价（实付）", U.green("¥%s" % _num(avg_paid))))
    U.out()

    U.out(U.rule())
    U.out(U.bold("  ♥ 最爱门店 TOP3"))
    U.out(U.rule())
    vmax = max(stores.values()) if stores else 1
    for name, cnt in stores.most_common(3):
        U.out("  %s %-*s %s" % (U.brand(U.bar(cnt, vmax, 10)), 30, name,
                                U.bold("%d 次" % cnt)))
    U.out()

    U.out(U.rule())
    U.out(U.bold("  ★ 点得最多的餐品 TOP5"))
    U.out(U.rule())
    vmax2 = max(items.values()) if items else 1
    for name, cnt in items.most_common(5):
        U.out("  %s %-*s %s" % (U.cyan(U.bar(cnt, vmax2, 10)), 30, name,
                                U.bold("%d 份" % cnt)))
    U.out()

    # 消费能力侧写
    top_store, top_cnt = (stores.most_common(1) or [("-", 0)])[0]
    top_item, item_cnt = (items.most_common(1) or [("-", 0)])[0]
    U.out(U.rule())
    U.out(U.bold("  麦麦侧写"))
    U.out(U.rule())
    U.out("  · 你最常去：%s（%d/%d 单，占 %.0f%%）"
          % (U.bold(top_store), top_cnt, len(orders), 100.0 * top_cnt / len(orders)))
    U.out("  · 你最常点：%s（%d 份）" % (U.bold(top_item), item_cnt))
    if avg_paid >= 60:
        U.out("  · 客单价 ¥%s，属于%s" % (_num(avg_paid), U.brand("重度金主")))
    elif avg_paid >= 30:
        U.out("  · 客单价 ¥%s，%s" % (_num(avg_paid), U.brand("中度麦迷")))
    else:
        U.out("  · 客单价 ¥%s，%s" % (_num(avg_paid), U.green("轻度尝鲜型")))
    U.out("  · 建议：把卡包里 3 天内到期的券用掉，`python -m butler redeem` 看券能在哪家店用")
    U.out()
    return 0


# ================================================================ 9. redeem（差异化核心）


def cmd_redeem(client, args):
    """临期券 × 门店可用性闭环。

    这是本项目最核心的命令：别的项目告诉你「你有张券要过期了」，
    本命令继续回答「所以现在到底去哪家店用掉它」。
    组合方式：query-my-coupons（取临期券）→ query-nearby-stores（取门店）
              → query-store-coupons（逐店验证这张券能不能用）
    """
    horizon = args.window if args.window else 3
    today = date.today()
    U.out(U.title("%s 积值 · 券去哪张店能用" % MCD))
    U.out(U.grey("  今天 %s · 只看 %d 天内到期的券" % (today, horizon)))

    # 1) 临期券
    coupons, _ = fetch_all_coupons(client)
    urgent = []
    for c in coupons:
        d = P.days_left(c["end"], today)
        if d is not None and 0 <= d <= horizon:
            urgent.append((d, c))
    urgent.sort(key=lambda x: x[0])

    if not urgent:
        U.out()
        U.out(U.green("  ✓ %d 天内没有券要过期，不用跑这一趟。" % horizon))
        U.out()
        return 0
    U.out(U.kv("临期券", U.bold(U.red("%d 张" % len(urgent)))))

    # 2) 门店（用户的收藏/默认门店，keyword 可本地过滤）
    kw = (args.keyword or "").strip()
    params = {"beType": 1, "searchType": 1}
    if kw:
        params["keyword"] = kw
    payload = client.call_json("query-nearby-stores", params)
    stores = payload.get("data") or []
    if kw:
        kwl = kw.lower()
        stores = [s for s in stores
                  if kwl in (s.get("storeName") or "").lower()
                  or kwl in (s.get("address") or "").lower()]
    if not stores:
        U.out(U.kv("门店", U.yellow("没搜到可验证的门店")))
        U.out(U.grey("  用 --city 指定城市可按地理位置搜；或换个关键词。"))
        U.out()
        return 0
    limit = args.limit if args.limit else len(stores)
    stores = stores[:limit]
    U.out(U.kv("验证门店", "%d 家%s" % (len(stores), ("（关键词「%s」）" % kw) if kw else "")))
    U.out()

    # 3) 逐店调用 query-store-coupons 做交叉验证
    #    到店自取场景：orderType=1 + beType=1，且不传 beCode
    #    （实测 beType=2/5/6 时必传 beCode，否则服务端返回 code 600048）
    matrix = defaultdict(list)   # 券名 -> [(门店名, 门店号)]
    checked = 0
    for s in stores:
        code = s.get("storeCode")
        if not code:
            continue
        try:
            data = client.call_json(
                "query-store-coupons",
                {"storeCode": code, "orderType": 1, "beType": 1},
            )
        except Exception:
            continue
        checked += 1
        for item in data.get("data") or []:
            title = item.get("title")
            if title:
                matrix[title].append((s.get("storeName") or code, code))

    U.out(U.rule())
    U.out(U.bold("  临期券 → 今天能用它的店"))
    U.out(U.rule())

    rescued, orphan = [], []
    for d, c in urgent:
        color, icon = _expiry_color(d)
        hits = matrix.get(c["name"]) or []
        U.out("  %s %s %s" % (color, U.bold(U.truncate(c["name"], 26)), icon))
        U.out("       %s" % U.grey("%s 到期 · %s" % (c["end"], _price(c["price"]) or "面额未标注")))
        if hits:
            names = "、".join(U.bold(U.truncate(h[0], 18)) for h in hits[:3])
            more = "等 %d 家" % len(hits) if len(hits) > 3 else ""
            U.out("       %s %s" % (U.green("✓ 可用："), names + U.grey(" " + more)))
            for name, code in hits[:3]:
                U.out("         %s %s" % (U.grey("门店号"), code))
            rescued.append((d, c, hits))
        else:
            U.out("       %s" % U.yellow("✗ 已验证的 %d 家门店都不支持这张券" % checked))
            orphan.append((d, c))
    U.out(U.rule())
    U.out()

    # 4) 行动结论
    if rescued:
        d, c, hits = rescued[0]
        when = "今天就用掉" if d == 0 else ("明天之前" if d == 1 else "%d 天内" % d)
        U.out(U.green(U.bold("  ✓ %d 张券能救，优先救最急的：" % len(rescued))))
        U.out("    %s → %s" % (U.bold(U.truncate(c["name"], 24)), U.bold(hits[0][0])))
        U.out("    %s 到期，%s。" % (c["end"], when))
    if orphan:
        U.out()
        U.out(U.yellow("  ⚠ %d 张券在已验证门店暂不可用：" % len(orphan)))
        for d, c in orphan[:3]:
            U.out("    · %s（%d 天后到期）—— 试试外送场景或换一家门店"
                  % (U.truncate(c["name"], 26), d))
    U.out()
    U.out(U.grey("  说明：以上「可用」是官方接口在该门店实时返回的结果，不是推测。"))
    U.out(U.grey("  门店范围来自你的收藏/默认门店（searchType=1）；加 --city 可按地理位置搜更多。"))
    U.out()
    return 0


# ================================================================ 10. value（积分资产运营，差异化核心）


def _face_value(name):
    """从商品名里提取可识别面值（元）。提不出就返回 None——不硬猜。"""
    if not name:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*元", name)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def cmd_value(client, args):
    """你的积分到底值多少钱、该怎么花。

    这是本项目最核心的命令。此前所有工具都在回答「什么要过期」，
    这个命令回答的是过期之前的那半句问题：**「那我该换成什么？」**

    串联 query-my-account（有多少分）→ mall-points-products（能换什么）
        → query-lottery-info（还有抽奖这条路）
    """
    U.out(U.title("%s 积值 Valor · 你的积分该怎么花" % MCD))

    # 1) 积分现状
    acc = fetch_account(client)
    avail = P.to_float(acc.get("availablePoint"))
    accumulative = P.to_float(acc.get("accumulativePoint"))
    expired = P.to_float(acc.get("expiredPoint"))

    U.out(U.kv("可用积分", U.bold("%s 分" % _num(avail)), color=U.brand))
    if expired > 0:
        U.out(U.kv("已过期", U.red("%s 分（占累计 %.0f%%）"
                             % (_num(expired), 100.0 * expired / accumulative if accumulative else 0))))
    U.out()

    # 2) 兑换商城
    goods = []
    try:
        payload = client.call_json("mall-points-products")
        goods = payload.get("data") or []
    except Exception as exc:
        U.out(U.yellow("  ⚠ 兑换商城查询失败：%s" % exc))
    if goods:
        goods = [g for g in goods if g.get("spuId")]
    U.out(U.grey("  兑换商城：%d 件在架商品" % len(goods)))
    U.out()

    # 2.1 性价比排名（能算出面值的才算，剩下单列）
    rows = []
    for g in goods:
        p = P.to_float(g.get("point"), -1)
        fv = _face_value(g.get("spuName"))
        rows.append({
            "name": g.get("spuName") or "-",
            "point": p,
            "face": fv,
            "cat": g.get("catName") or "-",
            "spu": g.get("spuId"),
            "down": g.get("downTime"),
        })

    priced = [r for r in rows if r["face"] and r["point"] > 0]
    unpriced = [r for r in rows if not (r["face"] and r["point"] > 0)]

    if priced:
        # 性价比 = 面值 / 积分（每 100 积分能换多少元）
        for r in priced:
            r["rate"] = r["face"] / r["point"] * 100.0
        priced.sort(key=lambda r: r["rate"], reverse=True)

        U.out(U.rule())
        U.out(U.bold("  ★ 兑换性价比排行 · 每 100 积分能换多少元"))
        U.out(U.rule())
        prows = []
        for r in priced[:10]:
            can = int(avail // r["point"]) if r["point"] > 0 else 0
            rate_color = U.green if r["rate"] >= 5 else (U.yellow if r["rate"] >= 2 else U.grey)
            prows.append([
                U.truncate(r["name"], 28),
                "%g" % r["point"],
                "¥%g" % r["face"],
                rate_color("¥%g" % round(r["rate"], 1)),
                (U.green("可换 %d 份" % can) if can else U.grey("积分不够")),
            ])
        U.out(U.table(["商品", "需积分", "面值", "每100分", "你现在"], prows,
                      ["l", "r", "r", "r", "l"]))
        U.out()

        best = priced[0]
        best_can = int(avail // best["point"])
        if best_can > 0:
            U.out(U.green(U.bold("  ✓ 最划算：%s" % U.bold(U.truncate(best["name"], 24)))))
            U.out("    %g 积分换 ¥%g，每 100 积分值 ¥%g；你的积分够换 %d 份。"
                  % (best["point"], best["face"], round(best["rate"], 1), best_can))
            U.out()

    if unpriced:
        U.out(U.grey("  以下商品不含明标价（多为派对/活动类，按场次核价），未参与性价比计算："))
        for r in unpriced[:6]:
            U.out(U.grey("    · %s%s" % (
                U.truncate(r["name"], 30),
                ("  %g 积分" % r["point"]) if r["point"] else "  积分待定")))
        U.out()

    # 3) 抽奖这条路
    try:
        lp = client.call_json("query-lottery-info")
        lot = lp.get("data") or {}
        if lot:
            draw_point = P.to_float(lot.get("drawPoint"))
            status_text = lot.get("activityStatusText") or "-"
            U.out(U.rule())
            U.out(U.bold("  🎰 另一条路：积分抽奖"))
            U.out(U.rule())
            U.out(U.kv("活动", "%s（%s）" % (lot.get("activityName") or "-", status_text)))
            U.out(U.kv("单次消耗", U.bold("%s 积分" % _num(draw_point)), color=U.brand))
            if draw_point > 0:
                times = int(avail // draw_point)
                U.out(U.kv("你的积分可抽", U.bold("%d 次" % times) if times else U.red("0 次")))
            prizes = lot.get("prizes") or []
            if prizes:
                U.out(U.kv("奖品池", "%d 种" % len(prizes)))
                ptxt = "、".join(p.get("name") or "?" for p in prizes[:5])
                U.out(U.kv("", U.grey(U.truncate(ptxt, 58))))
            dd = lot.get("drawDecision") or {}
            nc = dd.get("nextConsumption") or {}
            if dd.get("resourceEligible") and times > 0:
                U.out()
                U.out(U.yellow("  · 官方未公开各奖品的中奖概率，所以本工具不计算抽奖期望值——"))
                U.out(U.grey("    只如实告诉你成本与奖池。换不换由你决定。"))
                U.out(U.yellow("  · 建议：抽奖属于博彩，确定性收益优先选上面的「兑换」"))
            else:
                U.out()
                U.out(U.grey("  · 当前积分不足以参与抽奖，或活动未开放。"))
            U.out()
    except Exception as exc:
        U.out(U.grey("  · 抽奖信息查询失败：%s" % exc))

    # 4) 历史过期损失 → 换算成能换多少份
    if expired > 0 and priced:
        top = priced[0]
        lost_can = int(expired // top["point"]) if top["point"] > 0 else 0
        if lost_can > 0:
            U.out(U.rule())
            U.out(U.red(U.bold("  ⚑ 你已经白白过期的 %s 分，本可以换 %d 份「%s」"
                               % (_num(expired), lost_can, U.truncate(top["name"], 18)))))
            U.out(U.grey("    积分是会蒸发的。这一次，别让它再躺着过期。"))
            U.out(U.rule())

    U.out(U.grey("  兑换入口：积分商城 App 或小程序，本工具只做决策支持，不代下单。"))
    U.out()
    return 0


# ================================================================ 11. prizes（抽奖奖品追踪）


def cmd_prizes(client, args):
    """抽奖抽到的奖品追踪 —— 积分资产生命周期的最后一环。

    积分链路：赚积分 → 换商品/抽奖 → 拿到奖品 → 奖品也会过期。
    前三环分别由 account/value 覆盖，这一环管最后的「奖品没来得及用」。
    """
    U.out(U.title("%s 积值 Valor · 抽奖奖品追踪" % MCD))

    payload = client.call_json("query-my-prizes", {"pageSize": "50"})
    data = payload.get("data") or {}
    prizes = data.get("prizes") or []

    if not prizes:
        U.out(U.yellow("  你还没有抽奖记录。"))
        U.out(U.grey("  抽奖入口：麦麦积分抽奖活动，`python -m butler value` 可看当前成本与奖池。"))
        U.out()
        return 0

    usable = [p for p in prizes if p.get("status") == 0]
    dead = [p for p in prizes if p.get("status") != 0]
    by_type = Counter(p.get("prizeTypeText") or "未知" for p in prizes)

    U.out(U.kv("奖品总数", U.bold("%d 个" % len(prizes))))
    U.out(U.kv("仍可用", U.green("%d 个" % len(usable))))
    if dead:
        U.out(U.kv("已失效", U.red("%d 个（白抽了）" % len(dead))))
    U.out(U.kv("类型分布", " · ".join("%s %d" % (k, v) for k, v in by_type.most_common())))
    U.out()

    # 可用奖品：先按可用时间紧迫度排（timeRemindText 形如「可用时间: 2026.03.27-2026.04.02」）
    def remind_key(p):
        m = re.search(r"(\d{4})[.\-/](\d{2})[.\-/](\d{2})\s*-\s*(\d{4})[.\-/](\d{2})[.\-/](\d{2})",
                      p.get("timeRemindText") or "")
        if m:
            try:
                end = date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
                return (0, (end - date.today()).days)
            except ValueError:
                pass
        return (1, 0)

    if usable:
        U.out(U.rule())
        U.out(U.bold("  ✓ 还能用的奖品"))
        U.out(U.rule())
        rows = []
        for p in sorted(usable, key=remind_key):
            note = (p.get("timeRemindText") or "").replace("可用时间: ", "")
            days = None
            m = re.search(r"(\d{4})[.\-/](\d{2})[.\-/](\d{2})\s*-\s*(\d{4})[.\-/](\d{2})[.\-/](\d{2})",
                          p.get("timeRemindText") or "")
            if m:
                try:
                    end = date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
                    days = (end - date.today()).days
                except ValueError:
                    pass
            if days is not None and days < 0:
                badge = U.red("已过期")
            elif days is not None and days <= 2:
                badge = U.red("%d 天后截止" % days)
            elif days is not None:
                badge = U.green("至 %s" % note[-10:])
            else:
                badge = U.grey("无有效期信息")
            rows.append([
                U.truncate(p.get("name") or "-", 24),
                p.get("prizeTypeText") or "-",
                (p.get("recordTime") or "-")[:10],
                badge,
            ])
        U.out(U.table(["奖品", "类型", "抽中日期", "状态"], rows, ["l", "l", "l", "l"]))
        U.out()

    if dead:
        U.out(U.rule())
        U.out(U.bold("  ✗ 已失效的奖品（这些积分白花了）"))
        U.out(U.rule())
        for p in sorted(dead, key=lambda x: x.get("recordTime") or ""):
            note = (p.get("timeRemindText") or "").replace("可用时间: ", "")
            U.out("  %s %s %s" % (U.red("✗"),
                                  U.bold(U.truncate(p.get("name") or "-", 22)),
                                  U.grey("%s · 可用期 %s" % (p.get("recordTime", "")[:10], note))))
        U.out(U.rule())
        U.out()
        lost = len(dead)
        U.out(U.red(U.bold("  ⚑ 抽中却没用的奖品：%d 个" % lost)))
        if by_type.get("优惠券"):
            U.out(U.grey("    抽奖抽到的优惠券最容易忘——它躺在奖品列表里，不在卡包里，"))
            U.out(U.grey("    所以连 `coupons` 都看不到它们。这是被漏掉的一整类资产。"))
        U.out()

    if usable or dead:
        U.out(U.grey("  数据来自官方 query-my-prizes，含奖品状态与可用期。"))
        U.out()
    return 0


COMMANDS = {
    "account": cmd_account,
    "coupons": cmd_coupons,
    "claim": cmd_claim,
    "expiring": cmd_expiring,
    "nutrition": cmd_nutrition,
    "stores": cmd_stores,
    "calendar": cmd_calendar,
    "spend": cmd_spend,
    "redeem": cmd_redeem,
    "value": cmd_value,
    "prizes": cmd_prizes,
}
