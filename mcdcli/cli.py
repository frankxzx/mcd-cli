"""mcd — 把麦当劳装进你的 $PATH。npm / unix 风格的点餐 CLI（只读 + dry-run）。"""
import argparse, json, os, random, sys, time

from .backend import backend
from .data import nutrition_index, match

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
