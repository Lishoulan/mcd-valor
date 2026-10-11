# examples/ · 真实运行样例

这里的每一个 `.txt` 都是 **`python -m butler <命令>` 的真实运行输出**，
由真实麦当劳 MCP Token 调用生成，**没有任何手写美化或编造数据**。

- **生成时间**：2026-10-11
- **MCP Server**：`mcd-mcp` v1.0.9 · `https://mcp.mcd.cn`
- **脱敏**：`account.txt` 中的账户 ID 已替换为 `<已脱敏>`；所有文件均不含 Token

## 怎么复现

```bash
export MCD_MCP_TOKEN=你的Token     # https://open.mcd.cn/mcp 申请
python -m butler value > examples/value.txt
# ...依此类推
```

## 各文件说明

| 文件 | 对应命令 | 值得看的地方 |
| --- | --- | --- |
| **`value.txt`** | `python -m butler value` | **50 积分能换 18.8 元鸡腿堡**（每 100 积分值 37.6 元）；末尾「已过期 2902.9 分，本可以换 58 份」 |
| **`redeem.txt`** | `python -m butler redeem` | **7 张临期券里只有 2 张能用** —— 绿色「✓ 可用」与红色「✗ 不支持」逐条交叉 |
| **`prizes.txt`** | `python -m butler prizes` | 19 个抽奖奖品中 **3 个已失效**，而它们不在卡包里 |
| `account.txt` | `python -m butler account` | 累计 6345.4 分里 **2902.9 分（46%）已过期** |
| `coupons.txt` | `python -m butler coupons` | 16 张券按临期度三色上色 |
| `expiring.txt` | `python -m butler expiring` | 积分与券合并成一条倒计时 |
| `nutrition.txt` | `python -m butler nutrition 麦满分` | 9 个变体热量 246→513 kcal，三色分级 |
| `stores.txt` | `python -m butler stores 爱联` | 门店编号与是否可预约 |
| `calendar.txt` | `python -m butler calendar` | 本月 12 天有活动 |
| `spend.txt` | `python -m butler spend` | 10 单 ¥229.7；餐品 TOP5 已展开套餐子项 |

## 关于数据会变

这些是**某个时间点的快照**。跨天之后会变化，这是正常的：

- 临期券会随日期推移而增减（`redeem.txt` 里的张数每天不同）
- 积分余额会随兑换而变
- 奖品会新增或失效

**唯一不变的是每个结论背后的逻辑** —— 那由代码决定，不由数据决定。
若样例与你跑出来的不一致，**以你的实际输出为准**。
