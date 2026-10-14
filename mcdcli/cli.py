"""mcd — 把麦当劳装进你的 $PATH。npm / unix 风格的点餐 CLI（只读 + dry-run）。"""
import argparse, json, os, random, sys, time

from .backend import backend
from .data import nutrition_index, match, join_menu_items
from .optimizer import Goal, PRESETS, optimize
from .planner import lunch_candidates, plan_week, DAYS
import datetime as dt

VERSION = "10.24.0"
HOME = os.path.expanduser(os.environ.get("MCD_HOME", "~/.mcd"))
Y, R, G, D, B, X = "\033[33m", "\033[31m", "\033[32m", "\033[2m", "\033[1m", "\033[0m"
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    Y = R = G = D = B = X = ""


def _state():
    p = os.path.join(HOME, "state.json")
    return json.load(open(p)) if os.path.exists(p) else {"store": None, "cart": []}


def _save(st):
    os.makedirs(HOME, exist_ok=True)
    json.dump(st, open(os.path.join(HOME, "state.json"), "w"), ensure_ascii=False, indent=1)


def _need_store(st, be):
    if st.get("store"):
        return st["store"]["storeCode"]
    if not be.live:
        st["store"] = be.stores("", "")[0]; _save(st); return st["store"]["storeCode"]
    sys.exit(f"{R}fatal:{X} 还没选门店。先运行 `mcd store search <城市> <关键词>` 再 `mcd store use <storeCode>`")


def _find(meals, q):
    if q in meals:
        return q
    hits = [c for c, m in meals.items() if q == m["name"]] or [c for c, m in meals.items() if q in m["name"]]
    if not hits:
        sys.exit(f"{R}npm ERR! 404{X} '{q}' is not in this menu. 试试 `mcd menu | grep {q[:2]}`")
    return min(hits, key=lambda c: len(meals[c]["name"]))


def cmd_store(a, st, be):
    if a.action == "search":
        for s in be.stores(a.args[0], " ".join(a.args[1:]) or a.args[0])[:8]:
            print(f"{Y}{s['storeCode']}{X}  {s['storeName']}  {D}{s.get('address','')} · {s.get('distance','?')}m{X}")
    elif a.action == "use":
        st["store"] = {"storeCode": a.args[0], "storeName": " ".join(a.args[1:]) or a.args[0]}; _save(st)
        print(f"Switched to store '{a.args[0]}'")
    else:
        print(st.get("store") or "no store selected")


def cmd_menu(a, st, be):
    cats, meals = be.menu(_need_store(st, be))
    for c in cats:
        if a.category and a.category not in c["name"]:
            continue
        for code in c["codes"]:
            m = meals[code]
            line = f"{c['name']:<10}\t{code:<11}\t{m['name']}\t¥{m['currentPrice']}"
            if a.grep and a.grep not in line:
                continue
            print(line)


def cmd_nutrition(a, st, be):
    idx = nutrition_index(be.nutrition())
    names = [" ".join(a.names)] if a.names else [it["name"] for it in st["cart"]]
    if not names:
        sys.exit("usage: mcd nutrition <餐品名>  (或先 mcd install 一些东西)")
    print(f"{B}{'餐品':<16}{'kcal':>6}{'蛋白':>6}{'脂肪':>6}{'碳水':>6}{'钠mg':>7}{X}")
    for n in names:
        r = match(n.split("（")[0], idx) or next((v for k, v in idx.items() if n in k), None)
        if not r:
            print(f"{n:<16}{D}  (官方营养库暂无){X}"); continue
        print(f"{r['name']:<16}{r['energyKcal']:>6.0f}{r['protein']:>6.0f}{r['fat']:>6.0f}{r['carbohydrate']:>6.0f}{r['sodium']:>7.0f}")


def cmd_install(a, st, be):
    t0 = time.time()
    _, meals = be.menu(_need_store(st, be))
    for q in a.items:
        name, _, qty = q.partition("@")
        code = _find(meals, name)
        qty = int(qty or 1)
        for it in st["cart"]:
            if it["code"] == code:
                it["qty"] += qty; break
        else:
            st["cart"].append({"code": code, "name": meals[code]["name"], "qty": qty, "price": float(meals[code]["currentPrice"])})
        print(f"{G}+{X} {meals[code]['name']}@{code} ×{qty}  ¥{meals[code]['currentPrice']}")
    _save(st)
    n = sum(i["qty"] for i in st["cart"])
    print(f"\nadded {len(a.items)} package{'s' if len(a.items) > 1 else ''}, and audited {n} packages in {time.time() - t0:.1f}s")
    print(f"{D}run `mcd audit` for details · `mcd checkout --dry-run` to build{X}")


def cmd_rm(a, st, be):
    before = len(st["cart"])
    st["cart"] = [i for i in st["cart"] if a.item not in (i["code"], i["name"]) and a.item not in i["name"]]
    _save(st); print(f"removed {before - len(st['cart'])} package(s)")


def cmd_ls(a, st, be):
    if not st["cart"]:
        print("(empty)  · try `mcd install 板烧鸡腿堡 可乐`"); return
    print(f"mcd-cart@1.0.24 {HOME}")
    for i, it in enumerate(st["cart"]):
        tee = "└──" if i == len(st["cart"]) - 1 else "├──"
        print(f"{tee} {it['name']}@{it['code']} ×{it['qty']}  {D}¥{it['price']:.1f}{X}")


def audit(cart, idx):
    tot = {"energyKcal": 0, "protein": 0, "fat": 0, "carbohydrate": 0, "sodium": 0}
    unknown = []
    for it in cart:
        r = match(it["name"].split("（")[0], idx)
        if not r:
            unknown.append(it["name"]); continue
        for k in tot:
            tot[k] += r[k] * it["qty"]
    issues = []
    if tot["sodium"] > 2000: issues.append(("high", f"钠 {tot['sodium']:.0f}mg，超过成人每日建议量（<2000mg）", "今天其他餐清淡些，多喝水"))
    elif tot["sodium"] > 1200: issues.append(("moderate", f"钠 {tot['sodium']:.0f}mg，约占每日建议量 {tot['sodium']/20:.0f}%", "饮品换成无糖/纯悦"))
    if tot["energyKcal"] > 1000: issues.append(("high", f"热量 {tot['energyKcal']:.0f} kcal，一餐偏多", "mcd rm 一份小食，或和同事分享"))
    if tot["energyKcal"] > 0 and tot["protein"] * 4 / tot["energyKcal"] < 0.12: issues.append(("low", f"蛋白质供能比仅 {tot['protein']*400/tot['energyKcal']:.0f}%", "加一份板烧/鸡翅/牛奶"))
    sugar_drinks = [it["name"] for it in cart if any(k in it["name"] for k in ("可乐", "雪碧", "奶昔", "麦旋风", "新地")) and "无糖" not in it["name"]]
    if sugar_drinks: issues.append(("low", f"含糖饮品/甜品: {'、'.join(sugar_drinks)}", "试试无糖可口可乐或纯悦"))
    return tot, issues, unknown


def cmd_audit(a, st, be):
    tot, issues, unknown = audit(st["cart"], nutrition_index(be.nutrition()))
    print(f"# mcd audit report\n")
    color = {"high": R, "moderate": Y, "low": D}
    for sev, msg, fix in issues:
        print(f"{color[sev]}{sev:<9}{X}{msg}\n{'':9}{D}fix: {fix}{X}")
    print(f"\n总计 {tot['energyKcal']:.0f} kcal · 蛋白 {tot['protein']:.0f}g · 脂肪 {tot['fat']:.0f}g · 碳水 {tot['carbohydrate']:.0f}g · 钠 {tot['sodium']:.0f}mg")
    if unknown: print(f"{D}skipped (no nutrition data): {'、'.join(unknown)}{X}")
    n = len(issues)
    print(f"\nfound {n} {'vulnerability' if n == 1 else 'vulnerabilities'}" + (f" ({', '.join(s for s,_,_ in issues)})" if n else f" {G}✓ 吃得很健康{X}"))
    return 1 if any(s == "high" for s, _, _ in issues) else 0


def cmd_coupon(a, st, be):
    store = st["store"]["storeCode"] if st.get("store") else None
    avail, usable = be.coupons(store)
    print(f"{B}COUPON{X}{'':24}{B}STATUS{X}")
    for c in avail: print(f"{c:<30}{Y}CAN_GET{X}")
    for c in usable: print(f"{c:<30}{G}USABLE@{store}{X}")
    print(f"\n{D}mcd 只读不领券：请在麦当劳 App / 小程序自行领取（或在 Skill 里明确要求后由 Agent 代领）{X}")


def cmd_cal(a, st, be):
    cal = be.calendar(); today = time.strftime("%Y-%m-%d")
    print(f"{B}      {time.strftime('%B %Y')}{X}")
    for d in sorted(cal):
        mark = f"{Y}▶{X}" if d == today else " "
        for t in cal[d][:2]:
            print(f"{mark} {d[5:]}  {t}")


def cmd_checkout(a, st, be):
    if not st["cart"]:
        sys.exit(f"{R}error:{X} nothing to build (cart is empty)")
    store = _need_store(st, be)
    if not a.dry_run:
        print(f"{R}✋ refusing to place a real order.{X}\n"
              "mcd-cli 只做 dry-run。真实下单请在 AI 助手里使用 Skill：Agent 会先复述门店、餐品与金额，"
              "你回复「确认下单」后才会调用 create-order。")
        return 2
    t0 = time.time()
    print(f"> mcd@{VERSION} build --dry-run\n> calculate-price --store {store}\n")
    d = be.price(store, [(i["code"], i["qty"]) for i in st["cart"]])
    for l in d.get("productList", []):
        print(f"  {G}✓{X} {l['productName']:<20} ×{l['quantity']}  ¥{l['subtotal']/100:.2f}")
    disc = d.get("discount", 0) / 100
    print(f"\n  subtotal ¥{d.get('originalPrice', 0)/100:.2f}" + (f"   discount -¥{disc:.2f}" if disc else ""))
    print(f"{B}  TOTAL    ¥{d['price']/100:.2f}{X}" + (f"  {D}(offline estimate){X}" if d.get("offline") else f"  {D}(live: calculate-price){X}"))
    print(f"\n{G}Build succeeded{X} in {time.time()-t0:.1f}s · 0 orders created · 0 yuan spent")
    return 0


def cmd_sudo(a, st, be):
    if a.rest[:4] == ["make", "me", "a", "burger"]:
        print("🍔 Okay.  (just kidding — `mcd install 巨无霸` 然后 `mcd checkout --dry-run`)")
    else:
        print("mcd is not in the sudoers file. This incident will be reported to 麦当劳叔叔.")


def cmd_fortune(a, st, be):
    print(random.choice(["It works on my machine. 🍟", "There are 10 kinds of people: those who order 麦辣 and those who order 板烧.",
                         "git commit -m 'fix: hunger'", "99 little bugs in the code… 先吃个巨无霸再说。",
                         "Premature optimization is the root of all evil. Premature 薯条 is not."]))



def cmd_fit(a, st, be):
    """麦门健身餐：按热量/蛋白质目标找最便宜组合。"""
    g = Goal(max_items=a.max_items, exclude=[x for x in (a.exclude or "").split(",") if x])
    for k, v in PRESETS.get(a.goal or "", {}).items():
        setattr(g, k, v)
    for k in ("max_kcal", "min_kcal", "min_protein", "max_fat", "max_carb", "max_sodium", "budget"):
        v = getattr(a, k, None)
        if v is not None:
            setattr(g, k, v)

    online = be.live
    store = st.get("store")
    if online:
        if a.city or a.keyword:
            hits = be.stores(a.city or "", a.keyword or a.city or "")
            if not hits:
                sys.exit(f"{R}error:{X} 没有找到门店")
            store = {"storeCode": hits[0]["storeCode"], "storeName": hits[0].get("storeName", "")}
            st["store"] = store; _save(st)
        store_code = _need_store(st, be)
        store = st["store"]
        nut = be.nutrition()
        _, meals = be.menu(store_code)
        items = join_menu_items(meals, nut)
        src = "实时 MCP"
        priced = True
    else:
        # prefer pre-joined fit snapshot; else join menu+nutrition
        fit_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "fit_snapshot.json")
        if os.path.exists(fit_path):
            snap = json.load(open(fit_path, encoding="utf-8"))
            items = snap["items"]; store = snap.get("store") or store
            src = "本地快照 " + snap.get("fetchedAt", ""); priced = True
        else:
            nut = be.nutrition(); _, meals = be.menu(_need_store(st, be) if st.get("store") else "offline")
            items = join_menu_items(meals, nut); src = "离线菜单+营养库"; priced = True

    plans = optimize(items, g, top=a.top, objective="price" if priced else "protein")
    verify = None
    if a.verify and be.live and plans and store:
        d = be.price(store["storeCode"], [(it["code"], it["quantity"]) for it in plans[0]["items"]])
        verify = {"price": d.get("price", 0) / 100, "originalPrice": d.get("originalPrice", 0) / 100}

    if a.json:
        print(json.dumps({"goal": g.__dict__, "store": store, "plans": plans, "verify": verify}, ensure_ascii=False, indent=1))
        return 0 if plans else 1

    print(f"{B}🍔 mcd fit{X} | 数据: {src}" + (f" | 门店: {store.get('storeName')}" if store else ""))
    tgt = f"目标: ≤{g.max_kcal:.0f}kcal, 蛋白≥{g.min_protein:.0f}g"
    if g.budget < 1e8: tgt += f", 预算≤¥{g.budget:.0f}"
    if g.max_fat < 1e8: tgt += f", 脂肪≤{g.max_fat:.0f}g"
    print(tgt + "\n")
    if not plans:
        print(f"{R}😢 没找到满足条件的组合{X}，试试放宽热量或蛋白质目标。"); return 1
    for i, p in enumerate(plans, 1):
        t = p["total"]
        print(f"方案 {i}" + (f"  ¥{t['price']:.1f}" if priced else ""))
        for it in p["items"]:
            q = f" ×{it['quantity']}" if it["quantity"] > 1 else ""
            pr = f"¥{it['price']:.1f}  " if priced else ""
            print(f"  - {it.get('menuName', it['name'])}{q}  {pr}{it['energyKcal']:.0f}kcal  蛋白{it['protein']:.0f}g")
        print(f"  合计: {t['energyKcal']:.0f} kcal | 蛋白质 {t['protein']:.0f}g | 脂肪 {t['fat']:.0f}g | 碳水 {t['carbohydrate']:.0f}g | 钠 {t['sodium']:.0f}mg")
        kc = max(t["energyKcal"], 1)
        print(f"  供能比: 蛋白 {t['protein']*4/kc*100:.0f}% · 脂肪 {t['fat']*9/kc*100:.0f}% · 碳水 {t['carbohydrate']*4/kc*100:.0f}%\n")
    if verify:
        print(f"{G}✅ calculate-price 实时校验方案 1: ¥{verify['price']:.2f}（原价 ¥{verify['originalPrice']:.2f}）{X}")
    print(f"{D}ℹ️ 营养数据来自麦当劳官方 MCP，仅供参考，不构成医疗或营养建议；价格以下单页为准。{X}")
    return 0


def _week_dates(today=None, n=7):
    d, out = today or dt.date.today(), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def cmd_week(a, st, be):
    """打工人周预算：一周午餐不重样。"""
    split = lambda s: [x for x in (s or "").split(",") if x]
    online = be.live
    store = st.get("store")
    if online:
        if a.city or a.keyword:
            hits = be.stores(a.city or "", a.keyword or a.city or "")
            if not hits:
                sys.exit(f"{R}error:{X} 没有找到门店")
            store = {"storeCode": hits[0]["storeCode"], "storeName": hits[0].get("storeName", "")}
            st["store"] = store; _save(st)
        store_code = _need_store(st, be)
        store = st["store"]
        cats, meals = be.menu(store_code)
        # attach tags from categories if present
        tags = {}
        for c in cats:
            for code in c.get("codes", []):
                tags.setdefault(code, set())
        meals2 = {k: dict(v, tags=sorted(tags.get(k, ()))) for k, v in meals.items()}
        cands = lunch_candidates(meals2)
        if not a.member:
            cands = [c for c in cands if "麦金卡" not in c.get("tags", [])]
        cal = be.calendar()
        coupons, store_coupons = be.coupons(store_code)
        src = "实时 MCP"
    else:
        week_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "week_snapshot.json")
        if os.path.exists(week_path):
            s = json.load(open(week_path, encoding="utf-8"))
            store = s["store"]; cands = s["candidates"]; cal = s.get("calendar", {})
            coupons = s.get("coupons", []); store_coupons = s.get("storeCoupons", [])
            if not a.member:
                cands = [c for c in cands if "麦金卡" not in c.get("tags", [])]
            src = "本地快照 " + s.get("fetchedAt", "")
        else:
            store_code = _need_store(st, be)
            store = st["store"]
            _, meals = be.menu(store_code)
            cands = lunch_candidates(meals)
            cal = be.calendar(); coupons, store_coupons = be.coupons(store_code)
            src = "离线菜单"

    plan = plan_week(cands, a.budget, a.days, split(a.prefer), split(a.exclude), a.max_same)
    dates = _week_dates()
    if a.json:
        print(json.dumps({"store": store, "plan": plan, "calendar": cal, "coupons": coupons}, ensure_ascii=False, indent=1))
        return 0 if plan else 1

    print(f"{B}💼 mcd week{X} | 数据: {src} | 门店: {(store or {}).get('storeName')}")
    print(f"预算 ¥{a.budget:.0f} / {a.days} 天（日均 ¥{a.budget / a.days:.1f}）\n")
    if not plan:
        cheapest = sorted(c["price"] for c in cands)[: a.days]
        need = sum(cheapest) if cheapest else 0
        print(f"{R}😢 预算不够 {a.days} 天不重样{X}，最低约 ¥{need:.1f}。试试提高预算或放宽 --max-same。")
        return 1
    total = sum(c["price"] for c in plan); orig = sum(c["originalPrice"] for c in plan)
    for i, c in enumerate(plan):
        d = dates[i]
        save = f"  省¥{c['originalPrice'] - c['price']:.1f}" if c["originalPrice"] > c["price"] else ""
        print(f"{DAYS[d.weekday()]} {d:%m-%d}  [{c['family']}] {c['name']:<16} ¥{c['price']:.1f}{save}")
        for t in (cal.get(d.isoformat(), []) or [])[:1]:
            print(f"           📅 当日活动: {t}")
    print(f"\n合计 ¥{total:.1f} / 预算 ¥{a.budget:.0f}，剩余 ¥{a.budget - total:.1f}；比单点原价省 ¥{orig - total:.1f}")
    if coupons:
        print("🎟️ 麦麦省可领券（只读展示）: " + "、".join(coupons[:6]))
    upcoming = [(d, t) for d, ts in sorted(cal.items()) if dates and d >= dates[0].isoformat() for t in ts][:3]
    if upcoming:
        print("📅 近期活动: " + "；".join(f"{d[5:]} {t}" for d, t in upcoming))
    print(f"{D}ℹ️ 价格来自门店菜单/calculate-price，以下单页为准。{X}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mcd", description="把麦当劳装进你的 $PATH 🍔")
    ap.add_argument("-v", "--version", action="version", version=f"mcd {VERSION} (程序员节特别版)")
    sp = ap.add_subparsers(dest="cmd")
    s = sp.add_parser("store", help="门店: search <城市> <关键词> | use <code> | show"); s.add_argument("action", nargs="?", default="show"); s.add_argument("args", nargs="*")
    s = sp.add_parser("menu", help="列出菜单，可配合 | grep"); s.add_argument("--grep"); s.add_argument("-c", "--category")
    s = sp.add_parser("nutrition", aliases=["nutr"], help="营养成分（不带参数=购物车）"); s.add_argument("names", nargs="*")
    s = sp.add_parser("install", aliases=["i", "add"], help="加入购物车，支持 名称@数量"); s.add_argument("items", nargs="+")
    s = sp.add_parser("rm", aliases=["uninstall"], help="移出购物车"); s.add_argument("item")
    sp.add_parser("ls", aliases=["cart"], help="依赖树式查看购物车")
    sp.add_parser("audit", help="营养安全审计")
    s = sp.add_parser("coupon", help="coupon ls：可领/可用券（只读）"); s.add_argument("action", nargs="?", default="ls")
    sp.add_parser("cal", help="活动日历")
    s = sp.add_parser("price", help="price add <餐品>... | price ls"); s.add_argument("action"); s.add_argument("items", nargs="*")
    s = sp.add_parser("checkout", aliases=["build"], help="--dry-run: 调用 calculate-price 出小票"); s.add_argument("--dry-run", action="store_true")
    s = sp.add_parser("sudo"); s.add_argument("rest", nargs="*")
    sp.add_parser("fortune")
    s = sp.add_parser("fit", help="麦门健身餐：按热量/蛋白目标找最便宜组合")
    s.add_argument("--goal", choices=list(PRESETS))
    s.add_argument("--max-kcal", type=float); s.add_argument("--min-kcal", type=float)
    s.add_argument("--min-protein", type=float); s.add_argument("--max-fat", type=float)
    s.add_argument("--max-carb", type=float); s.add_argument("--max-sodium", type=float)
    s.add_argument("--budget", type=float); s.add_argument("--max-items", type=int, default=4)
    s.add_argument("--exclude", default=""); s.add_argument("--city"); s.add_argument("--keyword")
    s.add_argument("--verify", action="store_true"); s.add_argument("--top", type=int, default=3)
    s.add_argument("--json", action="store_true")
    s = sp.add_parser("week", help="打工人周预算：一周午餐不重样")
    s.add_argument("--budget", type=float, required=True)
    s.add_argument("--days", type=int, default=5)
    s.add_argument("--city"); s.add_argument("--keyword")
    s.add_argument("--prefer", default=""); s.add_argument("--exclude", default="")
    s.add_argument("--max-same", type=int, default=2)
    s.add_argument("--member", action="store_true")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help(); return 0
    if a.cmd == "price":  # git-style alias: mcd price add X == mcd install X
        a.cmd = "install" if a.action == "add" else "ls"
    alias = {"nutr": "nutrition", "i": "install", "add": "install", "uninstall": "rm", "cart": "ls", "build": "checkout"}
    cmd = alias.get(a.cmd, a.cmd)
    st = _state()
    be = backend() if cmd not in ("sudo", "fortune", "ls", "rm") else None
    return globals()["cmd_" + cmd](a, st, be) or 0
