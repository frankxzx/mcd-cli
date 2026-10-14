"""Pick N distinct lunches within a weekly budget, maximising savings, with protein-family variety."""
import re

FAMILIES = [("牛", ("牛", "巨无霸", "安格斯", "吉士汉堡", "汉堡包", "大堡")),
            ("鱼", ("鱼", "鳕")),
            ("鸡", ("鸡", "板烧", "麦辣", "翅", "龙焰", "苹板", "辣")),
            ("猪", ("猪",))]
LUNCH_HINTS = ("套", "随心配", "单人餐")
NOT_LUNCH = ("双人", "四宫格", "随心拼", "亲子", "开心乐园", "十翅", "周边", "帽", "泷", "双全盒", "多人")
DAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def family(name):
    for fam, kws in FAMILIES:
        if any(k in name for k in kws):
            return fam
    return "其他"


def lunch_candidates(meals, member_tags=()):
    """meals: code -> {name, currentPrice, originalPrice, tags?}. Returns list of candidate dicts."""
    out = []
    for code, m in meals.items():
        n = m["name"]
        if not any(h in n for h in LUNCH_HINTS) or any(x in n for x in NOT_LUNCH):
            continue
        out.append({"code": code, "name": n, "price": float(m["currentPrice"]),
                    "originalPrice": float(m.get("originalPrice") or m["currentPrice"]),
                    "family": family(n), "tags": m.get("tags", [])})
    return out


def _arrange(chosen):
    """Order picks so that adjacent days differ in protein family when possible (greedy by remaining count)."""
    rest, out = list(chosen), []
    while rest:
        prev = out[-1]["family"] if out else None
        counts = {}
        for c in rest:
            counts[c["family"]] = counts.get(c["family"], 0) + 1
        opts = [c for c in rest if c["family"] != prev] or rest
        pick = max(opts, key=lambda c: (counts[c["family"]], -c["price"]))
        rest.remove(pick)
        out.append(pick)
    return out


def plan_week(cands, budget, days=5, prefer=(), exclude=(), max_family=2):
    """Exact search: choose `days` distinct lunches, total <= budget, each family used <= max_family times.
    Score = savings + 3*preference hits; ties -> cheaper. Returns ordered list or None."""
    cs = [c for c in cands if not any(x in c["name"] or x == c["family"] for x in exclude)]
    seen, uniq = set(), []
    for c in sorted(cs, key=lambda c: c["price"]):
        if c["name"] not in seen:
            seen.add(c["name"]); uniq.append(c)
    cs = uniq

    def val(c):
        return (c["originalPrice"] - c["price"]) + 3 * sum(p in c["name"] or p == c["family"] for p in prefer)

    cs.sort(key=lambda c: -val(c))
    vals = [val(c) for c in cs]
    prices_sorted = sorted(c["price"] for c in cs)
    best = {"score": None, "pick": None}

    def rec(i, pick, cost, score, fam):
        k = len(pick)
        if k == days:
            key = (round(score, 2), -cost)
            if best["score"] is None or key > best["score"]:
                best["score"], best["pick"] = key, list(pick)
            return
        if i >= len(cs) or len(cs) - i < days - k:
            return
        if cost + sum(prices_sorted[: days - k]) > budget + 1e-9:
            return
        if best["score"] is not None and score + sum(vals[i:i + days - k]) < best["score"][0] - 1e-9:
            return
        c = cs[i]
        if cost + c["price"] <= budget + 1e-9 and fam.get(c["family"], 0) < max_family:
            fam[c["family"]] = fam.get(c["family"], 0) + 1
            pick.append(c)
            rec(i + 1, pick, cost + c["price"], score + vals[i], fam)
            pick.pop(); fam[c["family"]] -= 1
        rec(i + 1, pick, cost, score, fam)

    rec(0, [], 0.0, 0.0, {})
    return _arrange(best["pick"]) if best["pick"] else None
