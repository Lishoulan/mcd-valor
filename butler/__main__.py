# -*- coding: utf-8 -*-
"""积值 · 命令行入口。"""

import argparse
import sys

from . import commands as C
from . import ui as U
from .client import (DEFAULT_ENDPOINT, TOKEN_ENV, TOKEN_URL, AuthError,
                     McdClient, McpError, RateLimitError)

BANNER = r"""
   ___         __    _
  / _ |__  __/ /___(_)_______  __
 | |_| / // // / __/ / ___/ _ \/ /
 |  _/ // //_/ /_/ / /__/  __/ /
 |_| |__//_/ \__,_/_/   \___/_/
"""


def build_parser():
    p = argparse.ArgumentParser(
        prog="python -m butler",
        description="积值 · 你的麦当劳钱包哨兵（数据来自麦当劳 MCP Server 实时查询）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python -m butler account                 积分账户总览
  python -m butler coupons                 券包全景 + 临期提醒
  python -m butler claim                   一键领券
  python -m butler expiring                3 天内什么要过期
  python -m butler redeem                  ★ 这张快过期的券，今天哪家店能用
  python -m butler nutrition 鸡腿堡        按关键词查热量
  python -m butler stores 深圳北 --city 深圳  搜门店
  python -m butler calendar --date 2026-10-15
  python -m butler spend                   消费报告

Token 从环境变量 %s 读取，申请地址 %s
""" % (TOKEN_ENV, TOKEN_URL),
    )
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="MCP 接入地址（默认 %s）" % DEFAULT_ENDPOINT)
    sub = p.add_subparsers(dest="command", metavar="<命令>")

    sub.add_parser("account", help="积分账户总览（含历史过期损失提醒）")

    sub.add_parser("coupons", help="我的全部券，按临期程度上色")

    sub.add_parser("claim", help="一键领取所有当前可领的券")

    sp = sub.add_parser("expiring", help="★ 积分 + 券包合并的过期倒计时清单")
    sp.add_argument("--window", type=int, default=3, metavar="N", help="提前几天提醒（默认 3）")

    sp = sub.add_parser("redeem", help="★★ 临期券去哪张店能用：券 × 门店可用性交叉验证")
    sp.add_argument("keyword", nargs="?", default="", help="门店名/地标关键词，用于缩小验证范围")
    sp.add_argument("--window", type=int, default=3, metavar="N", help="提前几天（默认 3）")
    sp.add_argument("--limit", type=int, default=0, metavar="N", help="最多验证几家门店（默认全部）")

    sub.add_parser("value", help="★★★ 积分该换成什么：性价比排行 + 抽奖决策")

    sp = sub.add_parser("nutrition", help="餐品营养/热量查询")
    sp.add_argument("keyword", nargs="?", default="", help="餐品关键词，如「鸡腿堡」「咖啡」")

    sp = sub.add_parser("stores", help="附近门店搜索")
    sp.add_argument("keyword", nargs="?", default="", help="门店名/地标关键词")
    sp.add_argument("--city", help="城市名；给了就按地理位置搜（searchType=2）")
    sp.add_argument("--dt", dest="drive_through", action="store_true", help="搜得来速车道取餐门店（beType=5）")

    sp = sub.add_parser("calendar", help="本月营销活动日历")
    sp.add_argument("--date", help="指定基准日期 yyyy-MM-dd，返回前后各一天")

    sub.add_parser("spend", help="历史订单消费报告")

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        U.out(U.brand(BANNER))
        parser.print_help()
        return 1

    try:
        with McdClient(endpoint=args.endpoint) as client:
            return C.COMMANDS[args.command](client, args) or 0
    except AuthError as exc:
        U.out("")
        U.out(U.red(U.bold("✗ 鉴权问题")))
        U.out(U.red("  " + str(exc).replace("\n", "\n  ")))
        U.out("")
        return 2
    except RateLimitError as exc:
        U.out("")
        U.out(U.yellow(U.bold("⏳ 触发官方限流")))
        U.out(U.yellow("  " + str(exc).replace("\n", "\n  ")))
        U.out("")
        return 4
    except McpError as exc:
        U.out("")
        U.out(U.red(U.bold("✗ 调用失败")))
        U.out(U.red("  " + str(exc).replace("\n", "\n  ")))
        U.out(U.grey("  排查：网络是否通 / Token 是否过期 / 稍后重试"))
        U.out("")
        return 3
    except KeyboardInterrupt:
        U.out("")
        U.out(U.yellow("已取消。"))
        return 130


if __name__ == "__main__":
    sys.exit(main())
