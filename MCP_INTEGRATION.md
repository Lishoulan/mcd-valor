# MCP 集成说明

本文说明积值如何对接麦当劳 MCP Server：用了哪些 Tool、协议怎么走、每个字段怎么解析、以及这套组合能解决什么真实问题。

---

## 1. 接入信息

| 项 | 值 |
| --- | --- |
| Server 名称 | `mcd-mcp` v1.0.0 |
| 接入地址 | `https://mcp.mcd.cn`（**根路径**） |
| 传输方式 | Streamable-HTTP（JSON-RPC 2.0 over POST） |
| 鉴权 | HTTP Header `Authorization: Bearer <token>` |
| Token 申请 | <https://open.mcd.cn/mcp> |
| 协议版本 | `2024-11-05` |

> **踩坑提示**：地址是根路径 `https://mcp.mcd.cn`。按 MCP 惯例猜成 `https://mcp.mcd.cn/mcp` 会返回 `{"error_msg":"404 Route Not Found"}`。`/sse`、`/message` 同样 404——服务端只提供 Streamable-HTTP，不提供旧版 SSE。

### Header 要求

```
Authorization: Bearer <token>
Content-Type: application/json
Accept: application/json, text/event-stream
```

`Accept` 必须同时声明两种类型，否则部分网关会返回 406。

---

## 2. 调用流程

```
┌─────────┐                ┌──────────┐
│  butler │                            │
└────┬────┘                            │
     │ ① POST initialize                │
     │─────────────────────────────────▶│  返回 serverInfo / protocolVersion
     │◀─────────────────────────────────│
     │                                 │
     │ ② POST notifications/initialized │  ← 通知，无 id，不等回复
     │─────────────────────────────────▶│
     │                                 │
     │ ③ POST tools/call│
     │─────────────────────────────────▶│  返回 content[].text
     │◀─────────────────────────────────│
┘────┴─────────────────────────────────┘
```

对应 `butler/client.py`：

| 步骤 | 方法 | 说明 |
| --- | --- | --- |
| ① | `McdClient.initialize()` | 带 `protocolVersion` / `capabilities` / `clientInfo` |
| ② | 紧随其后自动发送 | `notifications/initialized`，`expect_reply=False`，失败不阻断（部分实现不要求） |
| ③ | `McdClient.call_tool(name, args)` | 统一出口，自动分配递增 `id` |

**Session 处理**：若响应头带 `Mcp-Session-Id`，客户端会记住并在后续所有请求回带（当前 `mcd-mcp` 未下发，属于向前兼容）。

**错误分流**：

| 情况 | 抛出的异常 | 终端提示 |
| --- | --- | --- |
| HTTP 401 / 403 | `AuthError` | Token 无效或过期 |
| HTTP 429 | `RateLimitError` | 触发官方限流，提示稍候重试 / 减少 `--limit` |
| 其他 HTTP 错误 | `McpError` | 带状态码与响应体前 300 字 |
| `URLError`（连不上） | `McpError` | 检查网络或代理 |
| JSON-RPC `error` 字段 | `McpError` | 带 MCP 错误码与消息 |
| 业务错误（`success:false`） | `McpError` | 带业务 `code` 与 `message`，如 `600048` |
| 空响应 | `McpError` | 带请求 id |

### 官方限流

> 每个 Token 每分钟最多允许 **600 次请求**，超过限制返回 **429**。
> 官方文档列明的错误码只有两个：**401**（Token 无效/过期/未提供）与 **429**（限流）。

这是唯一需要在设计时预留余量的约束：`redeem` 会为每张临期券 × 每家门店
调用一次 `query-store-coupons`，请求数随门店数线性增长。
因此 `redeem` 提供 `--limit N` 参数来限制验证门店数，
并在命中限流时给出明确的中文提示而非抛出原始异常。
以当前 3 家门店计算，单次 `redeem` 约发起 6 次请求，远低于上限。

---

## 3. 用到的 Tool

本项目实际调用 **7 个** Tool（`available-coupons` 仅在文档与规划中列出，未纳入命令）。

| Tool | 入参 | 返回形态 | 用于 |
| --- | --- | --- | --- |
| `query-my-account` | 无 | `## Original Response` + JSON | `account`、`expiring`、**`value`** |
| **`mall-points-products`** | `catRuleIds`（可选） | `## Original Response` + JSON | **`value`**（核心） |
| **`query-lottery-info`** | 无 | `## Original Response` + JSON | **`value`**（抽奖决策） |
| **`query-my-prizes`** | `pageNum`、`pageSize` | `## Original Response` + JSON | **`prizes`**（奖品追踪） |
| `query-my-coupons` | `page`、`pageSize`（字符串） | **纯 Markdown** | `coupons`、`expiring`、`claim`、**`redeem`** |
| **`query-store-coupons`** | `storeCode`、`orderType`、`beType`、可选 `beCode` | `## Original Response` + JSON | **`redeem`**（核心） |
| `auto-bind-coupons` | 无 | **纯 Markdown**（成功/失败文案） | `claim` |
| `list-nutrition-foods` | 无 | JSON 的 `data` 是 **CSV 字符串** | `nutrition` |
| `query-nearby-stores` | `beType`、`searchType`、`city`、`keyword` | 字段说明 + **多行缩进裸 JSON** | `stores`、**`redeem`** |
| `campaign-calendar` | `specifiedDate`（可选） | **纯 Markdown** | `calendar` |
| `order-list` | 无 | `## Original Response` + JSON | `spend` |

服务端官方共提供 **31 个 Tool**（含下单、门店菜单、积分商城、活动派对、积分抽奖等），
本项目使用其中 **12 个**，聚焦**积分资产生命周期管理**这一定位：11 个纯只读 + 1 个领券写操作。

---

## 3.0 核心组合：`value` 的三Tool 交叉

这是本项目区别于同类项目的关键设计。对比 `redeem` 解决「券去哪用」，
`value` 解决的是更前置的问题：**积分该换成什么**。

```text
query-my-account        →  「我有 1583.5 分，已过期 2902.9 分」
mall-points-products    →  「50 件商品，50 积分能换 18.8 元鸡腿堡」
query-lottery-info      →  「另一条路：24 积分抽一次，27 种奖品」
        └────────────── 交叉 ──────────────┘
                            ↓
        「每 100 积分值 37.6 元。你能换 31 份鸡腿堡。
          而过期的 2902.9 分本可以换 58 份。」
```

### 为什么这个组合有价值

实测数据揭示了一个反直觉的事实：**麦当劳积分商城里没有大额奖品**。

| 商品 | 需积分 | 面值 | 每 100 积分值|
| --- | --- | --- | --- |
| 18.8元麦辣鸡腿汉堡两件套 | 50 | ¥18.8 | **¥37.6** |
| 18.8元板烧鸡腿堡两件套 | 100 | ¥18.8 | ¥18.8 |
| 6.9元香芋派/菠萝派任选 | 50 | ¥6.9 | ¥13.8 |
| 18.8元2份麦辣鸡翅 | 200 | ¥18.8 | ¥9.4 |

50 积分换 18.8 元是全目录最优解（每 100 积分值 37.6 元）。
这直接推翻了「攒积分换大件」的常识——**积分是消耗品，不是资产**，
越囤越贬值。而多数积分工具只告诉你「要过期了」，
不告诉你「过期前应该换成什么」。

### 字段映射：mall-points-products

```json
{"success": true, "code": 200, "data": [
  {"spuName": "18.8元麦辣鸡腿汉堡两件套", "spuId": 6113,
   "point": "50", "price": "0", "shopId": 2, "status": 2,
   "catName": "到店专用", "upTime": "...", "downTime": "...",
   "spuImage": "...", "selling": "18.8元麦辣鸡腿汉堡两件套"}
]}
```

| 字段 | 用途 |
| --- | --- |
| `spuName` | **用正则提取 `(\d+(?:\.\d+)?)元` 得到面值** —— 唯一的面值来源 |
| `point` | 所需积分（字符串，需 `float()`） |
| `spuId` | 兑换时的 skuId（**本项目不调用下单，仅展示**） |
| `catName` | 适用范围（到店专用 / 其它） |
| `downTime` | 下架时间，可判断是否即将失效 |

**关键取舍**：`spuName` 里提不出面值的商品（如「麦当劳奇妙生日派对」）
**不参与性价比计算**，单独列在「不含明标价」区块。
理由：派对类按场次核价，用商品名前缀猜面值就是编数据。

### 字段映射：query-lottery-info

```json
{"data": {
  "activityName": "周六麦金喜抽奖", "activityStatusText": "进行中",
  "drawPoint": "24", "availablePoint": "1583.5",
  "drawDecision": {"resourceEligible": true,
                   "nextConsumption": {"type":"POINTS","points":"24","text":"本次将消耗 24 积分"}},
  "prizes": [{"name": "积分霸王餐", "imageUrl": "...", "typeText": "优惠券"}]
}}
```

| 字段 | 用途 |
| --- | --- |
| `drawPoint` | 单次消耗积分 |
| `drawDecision.resourceEligible` | 是否够资格参与（**必须看这个，不能看 availablePoint 自行推断**） |
| `drawDecision.nextConsumption` | 本次实际扣减说明 |
| `prizes[]` | 奖池清单（**只有 name/typeText/imageUrl，无概率**） |

**这里体现了本项目的一条底线**：`prizes` 里**没有任何中奖概率或权重字段**。
所以 `value` **明确拒绝计算抽奖期望值**——概率未知时算期望就是编造。
只如实输出单次成本、可抽次数、奖池清单，并附一句
「抽奖属于博彩，确定性收益优先选兑换」，把决策权交还用户。

---

## 3.05 核心组合：`prizes` 揭示的第三类资产盲区

前两个组合（`value`、`redeem`）覆盖了「积分」和「卡包里的券」。
但实测发现麦当劳 MCP 里还有**第三类资产**，它藏在一个大多数工具都忽略的地方：

```text
query-my-prizes     →  「你抽中过 19 个奖品，其中 3 个已失效」
                          ↓
        「抽奖抽到的券躺在奖品列表里，不在卡包里 ——
          连 query-my-coupons 都看不到它们。」
```

**关键发现**：`query-my-coupons`（查卡包券）和 `query-my-prizes`（查奖品）
是**两个完全独立的数据源**。抽奖抽到的券只在后者里：

```json
{"data": {"status": {...}, "prizes": [
  {"id": "...", "name": "麦辣三件套4折券", "prizeType": 4,
   "prizeTypeText": "优惠券", "recordTime": "2026-03-27 11:53:23",
   "status": 2, "statusText": "已失效",
   "timeRemindText": "可用时间: 2026.03.27-2026.04.02"}
]}}
```

| 字段 | 用途 |
| --- | --- |
| `name` / `prizeTypeText` | 奖品名与类型（实测该账户：门票 16 · 优惠券 3） |
| `recordTime` | 抽中时间（用于排序） |
| `status` / `statusText` | `0`=可用（实测值）；非 0 即失效 |
| `timeRemindText` | 可用期，形如 `可用时间: 2026.03.27-2026.04.02`，**仅失效奖品有此字段** |

**实测数据（2026-10-11）**：19 个奖品里 16 个可用、**3 个已失效**，
全是抽奖抽到的优惠券，可用期只有 6 天（3.27-4.02）却没人用。

**为什么这个发现重要**：任何只调用 `query-my-coupons` 的临期提醒工具
（包括很可能存在的同类参赛作品）**结构性看不到这批券**——
它们不在卡包里。这类资产需要主动去 `query-my-prizes` 才能发现。

因此本项目的 `prizes` 命令专门负责这一段生命周期：
**积分 → 抽奖 → 奖品 → 奖品失效**，前三环分别由 `account`/`value`/`prizes` 覆盖。

> 注意 `status` 的取值分布不均匀（实测只观察到 0 和 2），
> 所以代码用 `status == 0` 判可用、`!= 0` 判失效，而不是硬编码某个失效值。

---



## 3.1 核心组合：`redeem` 的三 Tool 交叉

这是本项目区别于同类项目的关键设计。单看任一Tool 都只能得到半截答案：

```text
query-my-coupons        →  「你有 6 张券3 天内过期」
query-nearby-stores     →  「你附近有 3 家店」
query-store-coupons     →  「这张券在这家店能不能用」
        └──────────── 交叉 ────────────┘
                            ↓
              「6 张券里只有 2 张今天能用，剩下 4 张必定归零」
```

**实测结果**（2026-10-10 真实 Token）：

|临期券 | 到期 | 可用门店数 |
| --- | --- | --- |
| 巧克力新地感谢券 ¥5 | 2026-10-11（1 天） | **2 家可用** |
| 9.9元中杯冰美式 ¥9.9 | 2026-10-12（2 天） | **2 家可用** |
| 巧克力味厚松饼猪柳蛋套餐 ¥29.9 | 2026-10-11（1 天） | 0 家 |
| 人气麦旋风买一送一 ¥15 | 2026-10-11（1 天） | 0 家 |
| 火腿扒堡早餐两件套 ¥9.9 | 2026-10-12（2 天） | 0 家 |
| 芝香脆鸡扒堡早餐两件套 ¥9.9 | 2026-10-13（3 天） | 0 家 |

**这个交叉结果是本项目的全部价值所在** —— 6 张「都要过期」的券，
真正能救的只有 2 张。只做提醒的工具会让用户为另外 4 张白跑一趟店。

### query-store-coupons 的入参约束（实测踩坑）

| 场景 | `orderType` | `beType` | `beCode` |
| --- | --- | --- | --- |
| 到店自取 | `1` | `1` | **不传**（传了会报错） |
| 得来速 (DT) | `1` | `5` | **必传**（来自 `query-nearby-stores`） |
| 麦乐送外送 | `2` | `2` | **必传**（来自 `delivery-query-address`） |

违反约束时服务端返回**业务错误**而非HTTP 错误：

```json
{"success": false, "code": 600048, "message": "外送场景下，beType=2/5/6时必传beCode"}
```

因此 `client.call_json` 会检查 `success is False` 并抛出带业务码的异常——
否则这个错误会以 `data` 为 `None` 的形式静默流过去，表现为「所有券都不可用」的假结论。

**踩坑细节**：收藏/默认门店（`searchType=1`）返回的门店对象里
**`beCode` 字段为 `None`**（而非空字符串），因为这些是到店自提场景的门店。
所以 `redeem` 固定用 `orderType=1 + beType=1` 且不传 `beCode`。

### 返回字段

```json
{"success": true, "code": 200, "data": [
  {
    "title": "巧克力新地感谢券",
    "couponId": "656620D152F4939E21E377A2C82678F4",
    "couponCode": "MCD608090AQG0900V7100",
    "tradeDateTime": "2026-09-28 00:00:00-2026-10-11 23:59:59",
    "products": [{"productCode": "4410", "productName": "朱古力新地"}],
    "promotionId": "110394002"
  }
]}
```

| 字段 | 用途 |
| --- | --- |
| `title` | **与 `query-my-coupons` 的券名做匹配键**（`redeem` 的交叉依据） |
| `tradeDateTime` | 券的门店可用时段，比卡包更精确 |
| `products[]` | 该券可用的餐品（可扩展成「该点哪个」建议） |
| `couponCode` / `couponId` | 下单时使用（本项目只读，不下单） |

> 门店不存在或不支持时返回 `data: []`（而非报错），所以**空数组是合法的「不可用」信号**，
> 不能与「请求失败」混为一谈。

---

## 4. 返回格式的五种形态（以及对应处理）

这是对接时最花时间的地方。`mcd-mcp` **不是**统一返回 JSON，而是把上游 API 响应包在一层自然语言说明里，且不同工具的包装方式不同。

### 形态A：`## Original Response` + JSON

`query-my-account`、`order-list`、`now-time-info`

```
# API Response Information

Below is the response from an API call. To help you understand the data, I've provided:

1. A detailed description of all fields in the response structure
2. The complete API response

## Response Structure

> Content-Type: application/json

- **code**:  (Type: integer)
- **data**: 积分账户信息 (Type: object)
  ...

## Original Response

{"success":true,"code":200,"message":"请求成功","data":{"availablePoint":"1583.5",...}}
```

处理：按 `## Original Response` 切分，取后半段 `json.loads`。

### 形态B：字段说明 + 换行缩进的裸 JSON

`query-nearby-stores` —— 注意它**没有** `## Original Response` 标记，JSON 直接贴在说明文字后面，而且是**多行缩进**的：

```
每个门店的基本信息按单行展示：
- **门店名称**: data[].storeName
- **门店地址**: data[].address
...
{"success":true,"code":200,"data":[{"storeCode":"1420887","storeName":"麦当劳深圳恒大城市之光(爱联)餐厅",...}]}
```

处理：**全文 `json.JSONDecoder().raw_decode()` 扫描**，取覆盖字符数最多的合法 JSON 值。逐行匹配会漏掉缩进的情况——这是实测踩过的坑。

### 形态C：纯 Markdown，无 JSON

`query-my-coupons`、`campaign-calendar`、`available-coupons`、`auto-bind-coupons`

券列表实测格式：

```
# 您的优惠券列表

共 16 张可用优惠券 | 第 1/1 页 | 每页 200 条

## 9.9元中杯冰美式
- **优惠**: ¥9.9 (用券价格)
- **有效期**: 2026-10-06 00:00-2026-10-12 23:59
- **领取时间**: 4日前收到
- **标签**: 到店专用、外送专用

<img src="https://...jpg" alt="9.9元中杯冰美式" height="auto" width="300">
```

活动日历实测格式（日期标题后可能带状态后缀，也可能没有）：

```
#### 2026年10月7日 往期回顾
-   **活动标题**：超值𝟗.𝟗元早餐两件套陪你开工啦😋
    **活动内容介绍**：早八的快乐，一堡一咖已就位🍔☕
#### 2026年10月10日 今日
#### 2026年10月11日← 未来日期无后缀
```

处理：全部交给 `parsers.py` 的正则。空券包返回固定文案 `暂无可用优惠券`，需单独判断，否则会解析出 0 张并误报「解析失败」。

### 形态D：JSON 里套CSV 字符串

`list-nutrition-foods`

```json
{"success":true,"code":200,"data":"[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:\n  猪柳麦满分,null,1288,308,16,16,24,781,213\n  中薯条,null,1210,289,4,12,38,165,18\n..."}
```

注意字段名是 `carbohydrate`（不是 `carb`），第二列 `nutritionDescription` 大量为字符串 `null`（不是 JSON `null`）。

处理：先 `json.loads` 拿到 `data` 字符串，再按 `:` 切出表体，逐行 `split(",")`，数值解析失败一律回落 0.0。

### 形态E：语义化成功/失败文案

`auto-bind-coupons` 不返回 JSON，只返回文案：

```
### 领券失败

错误信息：暂无可领取的优惠券
```

处理：正则匹配 `领券失败` / `错误信息`，把「暂无可领取」翻译成「券都领完了」这种对用户有意义的话，而不是把服务端原文直接甩出来。

---

## 5. 关键字段映射

### query-my-account → `data`

| 字段 | 含义 | 本项目用途 |
| --- | --- | --- |
| `availablePoint` | 可用积分 | `account` 主指标、`expiring` 概览 |
| `accumulativePoint` | 累计积分 | `account` |
| `usedPoint` | 已使用积分 | `account` |
| `expiredPoint` | **已过期积分（历史累计）** | `account` 的红色警告、`spend` 侧写 |
| `currentMouthExpirePoint` | 本月将过期 | `expiring` 的积分侧条目 |
| `nextMouthExpirePoint` | 下月将过期 | `account` |
| `lastMouthExpirePoint` | 上月已过期 | `account` |
| `frozenPoint` | 冻结积分 | `account`（非0 才显示） |

> **注意字段名拼写**：是 `currentMouthExpirePoint` —— 服务端把 `Month` 拼成了 `Mouth`。照直觉写 `currentMonthExpirePoint` 会静默取到空值。

所有数值字段都是**字符串**类型，需 `float()` 转换。

### query-my-coupons → Markdown 块

按 `^##\s+` 切块，每块解析：

| 目标 | 正则/方法 |
| --- | --- |
| 券名 | 块首行 |
| 优惠 | `\*\*优惠\*\*[:：]\s*(.+)` |
| 有效期 | `\*\*有效期\*\*[:：]\s*(.+)` 后用 `(\d{4}-\d{2}-\d{2})` 抓全部日期 |
| 领取时间 | `\*\*领取时间\*\*[:：]\s*(.+)` |
| 标签 | `\*\*标签\*\*[:：]\s*(.+)` 后按 `、,，/` 切分 |

**有效期的坑**：结束日期后面还跟着每日可用时段和星期限制：

```
2026-10-05 00:00-2026-10-11 23:59 10:00-22:00← 后面还有时段
2026-10-11 05:00-2026-10-11 10:29 周日 05:00-10:30      ← 还有星期 + 时段
```

分隔符是半角 `-`，按 `-` 切必然碎。正确做法是只认 `yyyy-MM-dd` 模式：第一个是开始、第二个是结束，其余丢弃。

> **另一个坑**：`re.findall` 在模式含多个分组时返回**元组列表**而非字符串列表。`DATE_RE.findall(period)` 拿到的是 `[('2026','10','06'), ...]`，必须改用 `finditer` 取 `group(0)`，否则日期解析静默返回 `None`（表现为「临期券数为 0」这种看起来像业务问题的 bug）。

**分页**：服务端上限 5 页 × 200 条。客户端按`page=1..5` 翻页，遇到「暂无可用优惠券」或返回条数不足 `pageSize` 即停止。实测该账户共 16 张券，单页取完。

### order-list → `data.list[]`

| 字段 | 说明 |
| --- | --- |
| `orderId` | 订单号 |
| `createTime` | 下单时间 `yyyy-MM-dd HH:mm:ss` |
| `storeName` | 门店名 → `spend` 的最爱门店 TOP3 |
| `realTotalAmount` | **实付金额（字符串）** → 总花费、客单价 |
| `orderStatus` | 订单状态 |
| `orderProductList[]` | 商品数组 |
| `orderProductList[].productName` / `quantity` | 商品名与数量 |
| `orderProductList[].comboItemList[]` | **套餐子项**（`name` / `quantity`） |

**统计口径**：餐品 TOP5 必须**展开 `comboItemList`**，否则「人气超值四件套随心选」会盖住真正的板烧鸡腿堡/中薯条/麦乐鸡。实测展开后中薯条 10 份居首，套餐名反而进不了 TOP5——这才是用户真正想知道的口径。

**0 元订单**：实测 10 单里有 4 单 `realTotalAmount=0`（积分兑换/赠券）。直接算客单价会失真，所以同时输出「客单价（全部）」和「客单价（实付）」两个口径。

### query-nearby-stores → `data[]`

| 字段 | 说明 |
| --- | --- |
| `storeName` / `storeCode` / `address` | 门店基本信息 |
| `distance` | 距离（实测收藏门店场景下恒为 `0`，故显示 `-`） |
| `reservation` | 是否支持预约 |
| `beCode` | 业务编码（仅 `beType=5` 得来速时有值） |

**关键词本地过滤的必要性**：实测 `searchType=1`（收藏/默认门店）时，服务端**忽略 `keyword` 参数** —— 搜「爱联」和搜「不存在的字符串xyz」返回完全相同的 3 家店。所以 `stores` 命令在拿到结果后按店名 + 地址本地再过滤一次，并明确告知用户「搜到 N 家但都不含关键词」。想让服务端真正按地理搜，必须传 `city` 使 `searchType=2`。

---

## 6. 业务价值

### 解决的真问题

**① 积分静默过期。** 麦当劳积分有有效期，但App 里过期提醒不够醒目。实测数据：累计 6345.4 分里已有 **2902.9 分（45.8%）过期**，而账户里`currentMouthExpirePoint` 是 0——也就是说用户当下没有紧迫感，历史已经亏掉近一半。`account` 把这个数字用红色打在最显眼的位置，`expiring` 每月末再预警一次。

**② 券包遗忘，且**知道了也用不掉。** 实测 16 张券里有 **6 张在 3 天内到期**，其中 3 张次日就到期。翻 App 找券包需要好几步操作，而 `expiring` 一条命令给出合并倒计时清单。

但**这还不够** —— 本项目实测发现：这 6 张券里**只有 2 张**在用户常去的 3 家门店可用，**另外 4 张必定归零**。这正是 `redeem` 存在的理由：它把「有什么要过期」推进到「**所以今天去哪家店用掉它**」。临期券是最容易被浪费的资产——它有真实面值（¥5/ ¥15/ ¥29.9）却会归零，而**盲目出门反而会白跑**。

**③ 领券不完整。** 麦当劳的活动分批上线，`available-coupons` 里的券需要手动逐张领。`claim` 调`auto-bind-coupons` 一键全领，并用领券前后的卡包张数做差值告诉你**实际新增了几张**（而不是只回一句「操作成功」）。

**④ 热量信息不可决策。** `nutrition` 把 160 条营养数据按热量升序排列并三色分级。实测「麦满分」9 个变体里热量从 246 到 513 kcal跨度 2 倍——用户能直接看出「加一层就翻倍」，而不是在营养成分表里手动对比。

**⑤ 消费无洞察。** `spend` 把10 条历史订单压成一张图：最爱门店、最常点、客单价档位。展开套餐子项后能看出「其实你最爱的是中薯条（10 份），不是那个四件套」。

### 与同类项目的差异

麦当劳 MCP 的 31 个 Tool 都能单独调用，但**「查券」与「查店」之间的那一步串联，目前没有其他参赛项目做**：

| 能力 | 多数临期提醒类项目 | 积值 |
| --- | --- | --- |
| 列出即将过期的券 | ✅ | ✅ |
| 告诉你过期时间与面额 | ✅ | ✅ |
| **告诉你这券今天哪家店能用** | ❌ | ✅ |
| **区分「能救」与「救不了」** | ❌ | ✅ |
| 门店不可用时说明原因 | — | ✅ 提示换场景/换门店 |

`redeem` 的输出把「6 张券要过期」这种**无行动价值的告警**，
转成「**去这家店用掉这张，另外 4 张别折腾了**」这种**可直接执行的结论**。

### 设计取向

- **行动优先于告警。** 告警本身没有价值，能被执行的动作才有。`redeem` 是这个取向的极致：它不告诉你「有券要过期」，它告诉你「现在去哪家店」。
- **过期 > 其它。** 命令默认窗口就是 3 天，且`expiring` 会把积分侧和券侧**合并成一条时间轴**——用户不该关心「积分」和「券」是两种资产，它们只是同一条倒计时上的不同条目。
- **诚实优先。** 每处数字都来自实时接口，没有 Mock。服务端返回「暂无可领取」就直说「券都领完了」，不包装成成功；门店返回空数组就如实说「这家店不支持」，不为了好看而模糊。
- **给可执行的下一步。** 空结果不只说「没有」，而是给出可直接复制的替代命令；券不可用时明确建议「试试外送场景或换一家门店」。
- **数字对齐。** 中文按 2 列宽计算表格宽度（`unicodedata.east_asian_width`），否则终端里全是错位的表格——一个数据工具如果表都对不齐，没人愿意看第二眼。

---

## 7. 复现验证

本文所有数据均可用以下命令复现（需自行配置 `MCD_MCP_TOKEN`）：

```bash
python -m butler value         # ★★★ 积分该换成什么：性价比排行 + 抽奖决策（招牌）
python -m butler prizes        # ★★ 抽奖奖品追踪：被漏掉的一整类资产
python -m butler redeem        # ★★ 临期券 × 门店可用性交叉验证
python -m butler account      # 积分账户，含历史过期损失
python -m butler coupons      # 券包全景
python -m butler expiring     # 3 天过期倒计时
python -m butler spend        # 消费报告
python -m butler nutrition 麦满分  # 营养数据过滤
python -m butler stores 爱联    # 门店搜索
python -m butler calendar     # 活动日历
python -m butler claim        # 一键领券（写操作）
```

回归测试：11 个命令（含参数变体共 15 次调用）全部通过，无异常抛出。

验证「代码里搜不到任何真实 Token」：

```bash
grep -rn "VQ91\|Bearer [A-Za-z0-9]\{20,\}" butler/ *.md *.json *.txt
# 期望：无输出（mcp-config.example.json 里只有 ${MCD_MCP_TOKEN} 占位符）
```
