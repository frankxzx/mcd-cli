"""Nutrition parsing + menu/nutrition matching."""
import json, re

COMBO_WORDS = ("件套", "双人", "多人", "拼盘", "小食盘", "随心", "开心乐园", "精选", "帽", "周边", "全明星", "双全盒", "十翅", "随心拼", "酱")


def parse_nutrition(raw):
    """Parse list-nutrition-foods `data` (TOON-like table) into list of dicts."""
    if isinstance(raw, dict):
        raw = raw.get("data", raw)
    if isinstance(raw, list):
        return raw
    lines = [l for l in raw.splitlines() if l.strip()]
    header = re.search(r"\{(.+)\}", lines[0]).group(1).split(",")
    out, seen = [], set()
    for l in lines[1:]:
        parts = [p.strip() for p in l.strip().rsplit(",", len(header) - 1)]
        if len(parts) != len(header):
            continue
        row = dict(zip(header, parts))
        if row["productName"] in seen:
            continue
        seen.add(row["productName"])
        item = {"name": row["productName"]}
        for k in ("energyKcal", "protein", "fat", "carbohydrate", "sodium"):
            try:
                item[k] = float(row[k])
            except ValueError:
                item[k] = 0.0
        out.append(item)
    return out


def norm(name):
    s = name.replace("（", "(").replace("）", ")").replace(" ", "")
    s = s.replace("“", "").replace("”", "").replace('"', "").replace("-", "").replace("™", "")
    s = s.replace("麦咖啡", "", 1) if s.startswith("麦咖啡") and len(s) > 3 else s
    s = re.sub(r"\(.*?\)", "", s) if "盒装" not in s else s
    return s


def nutrition_index(nut):
    idx = {}
    for n in nut:
        idx.setdefault(norm(n["name"]), n)
    return idx


def is_combo(name):
    return any(w in name for w in COMBO_WORDS)


def match(name, idx):
    """Return nutrition row for a menu name (tries exact, minus 套餐, size defaults)."""
    k = norm(name)
    bare = re.sub(r"\(.*?\)", "", k)
    for cand in (k, bare, k.replace("套餐", ""), k + "中杯", k + "5块"):
        if cand in idx:
            return idx[cand]
    return None
