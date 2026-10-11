"""模拟「什么都没有的新用户」：各接口返回空/零时的表现。

为什么需要这个：
  真实测试里我的账户有积分、有券、有门店，**空路径从没被走过**。
  而新用户装上工具的第一天就是空账户 —— 那条路径崩了就是第一印象崩了。

用法（**必须带真实 Token**，它只用于通过 MCP 初始化握手，
后续所有业务调用都被拦截替换，所以不会消耗你的配额）：
  export MCD_MCP_TOKEN=你的Token
  python tools/test_empty_account.py -q

方法：继承 McdClient，把指定 tool 替换成空返回，看命令是否优雅降级。
不改任何业务代码，纯黑盒。
"""
import sys
sys.path.insert(0, '.')
from butler.client import McdClient

EMPTY = {
    'query-my-account': {"availablePoint": "0", "accumulativePoint": "0",
                         "usedPoint": "0", "expiredPoint": "0",
                         "currentMouthExpirePoint": "0", "nextMouthExpirePoint": "0",
                         "lastMouthExpirePoint": "0", "frozenPoint": "0"},
    'query-my-coupons': {"data": {"list": []}},
    'query-nearby-stores': {"data": []},
    'mall-points-products': {"data": []},
    'query-lottery-info': {"data": {}},
    'query-my-prizes': {"data": {"prizes": []}},
    'order-list': {"data": {"list": []}},
    'campaign-calendar': {"data": []},
}


class EmptyClient(McdClient):
    def call_json(self, name, arguments=None):
        if name in EMPTY:
            return EMPTY[name]
        return {"data": []}

    def call_text(self, name, arguments=None):
        import json as _j
        if name in EMPTY:
            return _j.dumps(EMPTY[name], ensure_ascii=False)
        return _j.dumps({"data": []}, ensure_ascii=False)


def run(verbose=False):
    """跑一遍所有命令的空账户表现，返回出问题的命令列表。"""
    import butler.commands as C
    import traceback

    class A:
        window = 3
        limit = 0
        keyword = ""
        city = None
        date = None
        limit_stores = 0

    cases = ['account', 'coupons', 'expiring', 'redeem', 'value', 'prizes', 'spend', 'calendar']
    broken = []
    for cmd in cases:
        if verbose:
            print('=' * 46)
            print('【%s】全新空账户' % cmd)
            print('=' * 46)
        try:
            with EmptyClient() as c:
                C.COMMANDS[cmd](c, A())
            if verbose:
                print()
        except SystemExit:
            if verbose: print('  (正常退出)')
        except Exception as e:
            broken.append(cmd)
            print('  !!! %s 未捕获异常: %s' % (cmd, type(e).__name__))
            print('  ' + traceback.format_exc()[-380:])
    return broken


if __name__ == '__main__':
    import sys
    v = '-q' not in sys.argv
    bad = run(verbose=v)
    if bad:
        print('失败: %s' % ', '.join(bad))
        sys.exit(1)
    print('✓ 8 个命令在全新空账户下均优雅降级，无未捕获异常')