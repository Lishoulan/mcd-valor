# -*- coding: utf-8 -*-
"""麦门管家 · 麦当劳 MCP Streamable-HTTP 客户端（纯标准库实现）。

协议流程：
    initialize -> notifications/initialized -> tools/call

服务端把真正的业务 JSON 塞在返回 text 的 `## Original Response` 之后，
但并非所有工具都这么干（query-nearby-stores 直接把裸 JSON 甩在末尾），
所以 `extract_json` 两种都兼容。
"""

import json
import os
import urllib.error
import urllib.request

DEFAULT_ENDPOINT = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "mcd-butler"
CLIENT_VERSION = "1.0.0"
TOKEN_ENV = "MCD_MCP_TOKEN"
TOKEN_URL = "https://open.mcd.cn/mcp"

_MARKER = "## Original Response"


class McpError(Exception):
    """所有网络 / 协议层错误的基类。"""


class AuthError(McpError):
    """Token 缺失或被拒。"""


class RateLimitError(McpError):
    """触发官方限流（每 Token 每分钟最多 600 次请求）。"""


def get_token():
    """从环境变量读取 Token，绝不硬编码。"""
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        raise AuthError(
            "没有检测到环境变量 %s。\n"
            "  · Linux / macOS :  export %s=你的Token\n"
            "  · Windows CMD   :  set %s=你的Token\n"
            "  · PowerShell    :  $env:%s='你的Token'\n"
            "  · Token 申请地址:  %s"
            % (TOKEN_ENV, TOKEN_ENV, TOKEN_ENV, TOKEN_ENV, TOKEN_URL)
        )
    return token


def _unwrap_sse(raw):
    """Streamable-HTTP 可能返回 text/event-stream，取出 data: 行。"""
    raw = raw.strip()
    if not raw:
        return None
    if raw[0] in "{[":
        return raw
    for line in raw.splitlines():
        if line.startswith("data:"):
            return line[5:].strip()
    # 有些网关会返回 event:/id:/data: 混合体，退化为「取最长 JSON 行」
    best = None
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("{") or line.startswith("["):
            if best is None or len(line) > len(best):
                best = line
    return best


def extract_json(text):
    """从 MCP 返回的文本里挖出真 JSON。找不到返回 None。

    依次尝试：
      1. `## Original Response` 之后的部分
      2. 整段文本本身就是 JSON
      3. 全文扫描所有能被 raw_decode 成功解析的片段，取覆盖最长的那个
         （query-nearby-stores 会把 JSON 换行缩进后贴在说明文字后面，
           逐行匹配会漏掉，所以必须全文扫描）
    """
    if text is None:
        return None
    if isinstance(text, (dict, list)):
        return text
    text = text.strip()
    if not text:
        return None

    if _MARKER in text:
        tail = text.split(_MARKER, 1)[1].strip()
        obj = _decode_first(tail)
        if obj is not None:
            return obj

    if text[:1] in "{[":
        obj = _decode_first(text)
        if obj is not None:
            return obj

    return _scan_best(text)


def _decode_first(chunk):
    chunk = chunk.strip()
    if chunk[:1] not in "{[":
        return None
    try:
        return json.loads(chunk)
    except ValueError:
        pass
    # 尾部可能粘着多余文字，取第一个完整 JSON 值
    try:
        obj, _ = json.JSONDecoder().raw_decode(chunk)
        return obj
    except ValueError:
        return None


def _scan_best(text):
    """全文扫描，返回覆盖字符数最多的合法 JSON 值。"""
    decoder = json.JSONDecoder()
    best_obj, best_len = None, 0
    for i, ch in enumerate(text):
        if ch not in "{[":
            continue
        try:
            obj, end = decoder.raw_decode(text, i)
        except ValueError:
            continue
        span = end - i
        if isinstance(obj, (dict, list)) and span > best_len:
            best_obj, best_len = obj, span
    return best_obj


class McdClient(object):
    """麦当劳 MCP Server 的最小可用客户端。"""

    def __init__(self, endpoint=DEFAULT_ENDPOINT, token=None, timeout=90):
        self.endpoint = endpoint
        self.token = token or get_token()
        self.timeout = timeout
        self._id = 0
        self._sid = None  # Mcp-Session-Id，若服务端下发则后续请求需带上
        self.server_info = None
        self._detail_cache = {}   # spuId -> 是否可兑换（同一进程内只查一次）

    # ---------- 商品可兑换性 ----------
    def detail_available(self, spu_id):
        """商城商品现在还能不能兑换。

        `mall-points-products` 会把**已下架商品一并返回**，且：
          - `status` 恒为 2，区分不出来
          - `downTime` 对派对类（未来日期）也不可靠
        唯一权威判据是 `mall-product-detail`：下架商品返回 `610403 商品已下架`。
        结果缓存，避免同一进程内重复请求。
        """
        if spu_id is None:
            return False
        key = str(spu_id)
        if key in self._detail_cache:
            return self._detail_cache[key]
        try:
            self.call_json("mall-product-detail", {"spuId": key})
            ok = True
        except Exception as exc:
            msg = str(exc)
            # 610403 = 已下架；其他错误（网络等）不当成下架，按可用处理并留待人工判断
            ok = "610403" not in msg and "下架" not in msg
        self._detail_cache[key] = ok
        return ok

    # ---------- 底层 HTTP ----------
    def _post(self, payload, expect_reply=True):
        self._id += 1
        body = dict(payload)
        body["jsonrpc"] = "2.0"
        if expect_reply:
            body["id"] = self._id

        data = json.dumps(body).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "%s/%s" % (CLIENT_NAME, CLIENT_VERSION),
        }
        if self._sid:
            headers["Mcp-Session-Id"] = self._sid

        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
                if sid:
                    self._sid = sid
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            if exc.code in (401, 403):
                raise AuthError(
                    "MCP 服务拒绝了该 Token（HTTP %s）。请确认 %s 是否有效、是否已过期。\n%s"
                    % (exc.code, TOKEN_ENV, detail)
                )
            if exc.code == 429:
                raise RateLimitError(
                    "触发麦当劳 MCP 官方限流（每个 Token 每分钟最多 600 次请求）。\n"
                    "  · 请稍候几十秒后重试\n"
                    "  · 若用 redeem --limit 验证了很多门店，可减少 --limit 的值"
                )
            raise McpError("HTTP %s %s" % (exc.code, exc.reason) + ("\n" + detail if detail else ""))
        except urllib.error.URLError as exc:
            raise McpError("连不上 %s：%s\n请检查网络或代理设置。" % (self.endpoint, exc.reason))

        if not expect_reply:
            return None

        raw = _unwrap_sse(raw)
        if raw is None:
            raise McpError("服务端返回了空响应（id=%s）。" % self._id)
        try:
            envelope = json.loads(raw)
        except ValueError:
            raise McpError("无法解析服务端响应：%s" % raw[:200])

        if "error" in envelope:
            err = envelope["error"] or {}
            raise McpError("MCP 返回错误 [%s] %s" % (err.get("code"), err.get("message")))
        return envelope.get("result", {})

    # ---------- MCP 生命周期 ----------
    def initialize(self):
        result = self._post(
            {
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
                },
            }
        )
        self.server_info = result.get("serverInfo")
        # 通知服务端握手完成（无 id，不等回复）
        try:
            self._post({"method": "notifications/initialized", "params": {}}, expect_reply=False)
        except McpError:
            pass  # 部分实现不要求该通知，失败不阻断
        return result

    def connect(self):
        self.initialize()
        return self

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        return False

    # ---------- 工具调用 ----------
    def call_tool(self, name, arguments=None):
        """调用工具，返回 (完整文本, 解析出的JSON或None)。"""
        result = self._post(
            {"method": "tools/call", "params": {"name": name, "arguments": arguments or {}}}
        )
        chunks = []
        for item in result.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(item.get("text") or "")
        text = "\n".join(chunks)
        if result.get("isError") and not extract_json(text):
            raise McpError("工具 %s 返回错误：%s" % (name, text.strip()[:300]))
        return text, extract_json(text)

    def call_json(self, name, arguments=None):
        """只要 JSON 部分。"""
        text, obj = self.call_tool(name, arguments)
        if obj is None:
            raise McpError(
                "工具 %s 没有返回可解析的 JSON，原文前 200 字：%s" % (name, text.strip()[:200])
            )
        # 服务端会用 success=false + code 表达业务错误（如 beCode 缺失的 600048），
        # 这类不是传输层错误，所以放进异常里而不是直接抛 KeyError。
        if isinstance(obj, dict) and obj.get("success") is False:
            raise McpError(
                "工具 %s 返回业务错误 [%s]：%s"
                % (name, obj.get("code"), obj.get("message") or "无消息")
            )
        return obj

    def call_text(self, name, arguments=None):
        """只要文本部分（Markdown 型工具用）。"""
        return self.call_tool(name, arguments)[0]
