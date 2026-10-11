#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""积值 Valor · 跨天运行记录器

为什么需要这个
----------------
麦当劳的券每天在过期、每天有新的进账。所有参赛项目的 README 都只贴
**某一刻**的输出截图——读者无法判断那是真的还是编的。

这个脚本每天跑一次，把真实结果追加成时间序列。累积 7 天后，
`docs/RUN_LOG.md` 就是一份**别人抄不走的实证**：
证明这个项目真的在持续运行，而不是P 了一张好看的图。

用法：
    export MCD_MCP_TOKEN=你的Token
    python tools/record_run.py            # 记录今天
    python tools/record_run.py --show     # 只看已有记录

产物：
    examples/run-log.jsonl   每行一条：日期 + 关键指标（机器可读）
    docs/RUN_LOG.md               渲染成表格（人可读，随记录自动更新）
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from butler.client import McdClient  # noqa: E402
from butler import parsers as P     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSONL = os.path.join(ROOT, "examples", "run-log.jsonl")
MARKDOWN = os.path.join(ROOT, "docs", "RUN_LOG.md")


def snap(client, window=3):
    """抓一份当天的关键指标。任何一个环节失败都记None，不编造。"""
    out = {"date": date.today().isoformat(),
           "at": datetime.now().strftime("%H:%M:%S")}

    try:
        d = (client.call_json("query-my-account").get("data") or {})
        out["available_point"] = P.to_float(d.get("availablePoint"))
        out["expired_point"] = P.to_float(d.get("expiredPoint"))
    except Exception as e:
        out["account_error"] = str(e)[:80]

    try:
        coupons, total = [], None
        for page in (1, 2):
            txt = client.call_text("query-my-coupons",
                                   {"page": str(page), "pageSize": "200"})
            cs, t = P.parse_coupons(txt)
            total = total if total is not None else t
            coupons.extend(cs)
            if len(cs) < 200:
                break
        out["coupons_total"] = total if total is not None else len(coupons)
        soon = [(P.days_left(c["end"]), c) for c in coupons]
        due = [(d, c) for d, c in soon if d is not None and 0 <= d <= window]
        out["coupons_due"] = len(due)
        out["coupons_due_names"] = [c["name"] for _, c in sorted(due, key=lambda x: x[0])]
    except Exception as e:
        out["coupons_error"] = str(e)[:80]

    try:
        data = client.call_json("query-nearby-stores",
                                {"beType": 1, "searchType": 1}).get("data") or []
        out["stores"] = len(data)
        # 券 × 门店交叉：每家店查一次，数清哪些临期券真的能用
        usable = {}
        for s in data:
            code = s.get("storeCode")
            if not code:
                continue
            try:
                r = client.call_json("query-store-coupons",
                                     {"storeCode": code, "orderType": 1, "beType": 1})
            except Exception:
                continue
            for it in (r.get("data") or []):
                t = it.get("title")
                if t and t in out.get("coupons_due_names", []):
                    usable.setdefault(t, []).append(s.get("storeName") or code)
        out["rescuable"] = len(usable)
        out["rescue_detail"] = {k: len(v) for k, v in usable.items()}
    except Exception as e:
        out["store_error"] = str(e)[:80]

    try:
        pr = (client.call_json("query-my-prizes", {"pageSize": "50"}).get("data") or {})
        ps = pr.get("prizes") or []
        out["prizes_total"] = len(ps)
        out["prizes_dead"] = len([p for p in ps if p.get("status") != 0])
    except Exception as e:
        out["prizes_error"] = str(e)[:80]

    return out


def load_all():
    if not os.path.exists(JSONL):
        return []
    rows = []
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def render_md(rows):
    lines = [
        "# 📈 跨天运行记录",
        "",
        "> 这份文件由 `tools/record_run.py` **自动生成**，每次运行工具都会追加一行。",
        "> 下面的每一个数字都是当时真实调用麦当劳 MCP 的返回结果，**没有任何手写**。",
        "",
        "为什么值得看：券每天在过期、每天有新的进账。所有参赛项目的 README 都只贴",
        "**某一刻**的截图——而这里是一条随时间延伸的序列。**它证明这个项目真的在跑。**",
        "",
        "## 记录表",
        "",
        "| 日期 | 可用积分 | 已过期 | 券总数 | 3天内到期 | **能用掉的** | 奖品(失效) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        def g(k, fmt="%s"):
            v = r.get(k)
            if v is None:
                return "—"
            if k.endswith("point"):
                return fmt % (int(v) if float(v).is_integer() else round(v, 1))
            return str(v)
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s |" % (
                r.get("date", "?"), g("available_point"), g("expired_point"),
                g("coupons_total"), g("coupons_due"), g("rescuable"),
                "%s (%s)" % (g("prizes_total"), g("prizes_dead"))))
    lines += [
        "",
        "## 「能用掉的」这一列是关键",
        "",
        "它不是券包里的张数，而是**逐张券 × 逐家门店调用 `query-store-coupons`",
        "交叉验证后，真正能被用掉的张数**。",
        "",
        "通常它会明显小于「3 天内到期」——差值就是注定要归零的资产。",
        "",
        "## 复现",
        "",
        "```bash",
        "export MCD_MCP_TOKEN=你的Token",
        "python tools/record_run.py       # 记录今天",
        "python tools/record_run.py --show",
        "```",
        "",
        "原始数据在 `examples/run-log.jsonl`（每行一条 JSON，机器可读）。",
    ]
    return "\n".join(lines) + "\n"


def main():
    if "--show" in sys.argv:
        rows = load_all()
        if not rows:
            print("还没有记录。先跑一次：python tools/record_run.py")
        else:
            print(render_md(rows))
        return 0

    print("正在抓取今天的真实数据…")
    with McdClient() as client:
        snap_row = snap(client)

    rows = load_all()
    today = snap_row["date"]
    rows = [r for r in rows if r["date"] != today] + [snap_row]
    rows.sort(key=lambda r: r["date"])

    # 若当天已有记录且指标完全相同，保留原记录（含原 at 时间戳），
    # 避免 CI 每天数据没变也产生一次提交，污染提交历史。
    previous = next((r for r in load_all() if r["date"] == today), None)
    if previous and _same_metrics(previous, snap_row):
        print("今天的数据与已有记录完全一致，保留原时间戳。")
        snap_row = previous
        rows = [r for r in rows if r["date"] != today] + [snap_row]
        rows.sort(key=lambda r: r["date"])

    os.makedirs(os.path.dirname(JSONL), exist_ok=True)
    with open(JSONL, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    os.makedirs(os.path.dirname(MARKDOWN), exist_ok=True)
    with open(MARKDOWN, "w", encoding="utf-8") as f:
        f.write(render_md(rows))

    print("已记录 %s：" % today)
    for k in ("available_point", "expired_point", "coupons_total",
              "coupons_due", "rescuable", "prizes_total", "prizes_dead"):
        print("  %-18s %s" % (k, snap_row.get(k, "—")))
    print("\n累计 %d 天记录 -> docs/RUN_LOG.md" % len(rows))
    return 0


def _same_metrics(a, b):
    """忽略 at字段，比较实际指标。"""
    ignore = {"at"}
    ka = {k: v for k, v in a.items() if k not in ignore}
    kb = {k: v for k, v in b.items() if k not in ignore}
    return ka == kb

    with open(MARKDOWN, "w", encoding="utf-8") as f:
        f.write(render_md(rows))

    print("已记录 %s：" % today)
    for k in ("available_point", "expired_point", "coupons_total",
              "coupons_due", "rescuable", "prizes_total", "prizes_dead"):
        print("  %-18s %s" % (k, snap_row.get(k, "—")))
    print("\n累计 %d 天记录 -> docs/RUN_LOG.md" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
