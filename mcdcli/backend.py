"""Data backends: live MCP (read-only) or offline snapshot (MCD_OFFLINE=1)."""
import json, os
from .data import parse_nutrition

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
READ_ONLY_TOOLS = {"query-nearby-stores", "query-meals", "query-meal-detail", "calculate-price", "list-nutrition-foods",
                   "available-coupons", "query-store-coupons", "campaign-calendar", "now-time-info"}


def _load(name):
    return json.load(open(os.path.join(DATA, name), encoding="utf-8"))


class Offline:
    live = False

    def __init__(self):
        self.snap = _load("menu_snapshot.json")
        self.extras = _load("extras_snapshot.json")

    def stores(self, city, keyword):
        return [dict(self.snap["store"], address="（离线快照）", distance=0)]

    def menu(self, store):
        return self.snap["categories"], self.snap["meals"]

    def nutrition(self):
        return _load("nutrition.json")

    def price(self, store, items):
        meals = self.snap["meals"]
        lines = [{"productCode": c, "productName": meals[c]["name"], "quantity": q,
                  "subtotal": int(round(float(meals[c]["currentPrice"]) * 100)) * q} for c, q in items]
        total = sum(l["subtotal"] for l in lines)
        return {"price": total, "originalPrice": total, "discount": 0, "productList": lines, "offline": True}

    def coupons(self, store=None):
        return self.extras["coupons"], []

    def calendar(self):
        return self.extras["calendar"]


class Live:
    live = True

    def __init__(self):
        from .mcp_client import MCPClient
        self.c = MCPClient(); self.c.initialize()

    def call(self, tool, args=None):
        assert tool in READ_ONLY_TOOLS, f"mcd-cli 只调用只读工具，拒绝: {tool}"
        r = self.c.call(tool, args or {})
        if isinstance(r, dict) and r.get("success") is False:
            raise RuntimeError(r.get("message"))
        return r.get("data") if isinstance(r, dict) else r

    def stores(self, city, keyword):
        return self.call("query-nearby-stores", {"beType": 1, "searchType": 2, "city": city, "keyword": keyword}) or []

    def menu(self, store):
        d = self.call("query-meals", {"storeCode": store, "orderType": 1, "beType": 1})
        cats = [{"name": c["name"].replace("\n", ""), "codes": [m["code"] for m in c["meals"]]} for c in d["categories"]]
        return cats, d["meals"]

    def nutrition(self):
        return parse_nutrition(self.call("list-nutrition-foods"))

    def price(self, store, items):
        return self.call("calculate-price", {"storeCode": store, "orderType": 1, "beType": 1,
                                             "items": [{"productCode": c, "quantity": q} for c, q in items]})

    def coupons(self, store=None):
        avail = [c["couponName"] for c in self.call("available-coupons") or []]
        usable = []
        if store:
            usable = [c.get("couponName") or c.get("name") for c in
                      self.call("query-store-coupons", {"storeCode": store, "orderType": 1, "beType": 1}) or []]
        return sorted(set(avail)), usable

    def calendar(self):
        out = {}
        for d in (self.call("campaign-calendar") or {}).get("dailyList", []):
            ts = [(e.get("articleDto") or {}).get("title") or e.get("activityTitle") for e in d.get("events", [])]
            ts = [t.strip() for t in ts if t]
            if ts:
                out[d["date"]] = ts
        return out


def backend():
    return Offline() if os.environ.get("MCD_OFFLINE") == "1" else Live()
