"""Minimal streamable-HTTP MCP client for https://mcp.mcd.cn (stdlib only)."""
import json, os, urllib.request

DEFAULT_URL = "https://mcp.mcd.cn"


def load_token():
    tok = os.environ.get("MCD_MCP_TOKEN")
    if not tok:
        p = os.path.expanduser("~/.secrets/mcd_token")
        if os.path.exists(p):
            tok = open(p).read().strip()
    return tok


class MCPClient:
    def __init__(self, token=None, url=DEFAULT_URL, timeout=30):
        self.token = token or load_token()
        if not self.token:
            raise RuntimeError("缺少 MCD_MCP_TOKEN 环境变量")
        self.url, self.timeout, self.session, self._id = url, timeout, None, 0

    def _post(self, payload):
        h = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
             "Accept": "application/json, text/event-stream"}
        if self.session:
            h["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.url, json.dumps(payload).encode(), h)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            sid = r.headers.get("Mcp-Session-Id")
            if sid:
                self.session = sid
            body = r.read().decode("utf-8")
            if not body.strip():
                return None
            if "text/event-stream" in (r.headers.get("Content-Type") or ""):
                for line in body.splitlines():
                    if line.startswith("data:"):
                        d = json.loads(line[5:].strip())
                        if "id" in d:
                            return d
                return None
            return json.loads(body)

    def rpc(self, method, params=None):
        self._id += 1
        res = self._post({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}})
        if res and "error" in res:
            raise RuntimeError(res["error"])
        return (res or {}).get("result")

    def initialize(self):
        r = self.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                    "clientInfo": {"name": "mcd-cli", "version": "0.1.0"}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return r

    def call(self, name, args=None):
        r = self.rpc("tools/call", {"name": name, "arguments": args or {}})
        if r and r.get("structuredContent"):
            return r["structuredContent"]
        texts = [c.get("text", "") for c in (r or {}).get("content", []) if c.get("type") == "text"]
        t = "\n".join(texts)
        try:
            return json.loads(t)
        except Exception:
            return t
