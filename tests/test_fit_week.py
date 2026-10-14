import datetime as dt, itertools, json, os, tempfile, unittest

os.environ["MCD_OFFLINE"] = "1"
os.environ["NO_COLOR"] = "1"

from mcdcli import cli
from mcdcli.optimizer import Goal, optimize
from mcdcli.planner import family, lunch_candidates, plan_week
from mcdcli.data import parse_nutrition, nutrition_index, match, join_menu_items

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ITEMS = [
    dict(name="A", price=10, energyKcal=300, protein=20, fat=10, carbohydrate=30, sodium=500),
    dict(name="B", price=8, energyKcal=200, protein=15, fat=8, carbohydrate=10, sodium=400),
    dict(name="C", price=20, energyKcal=500, protein=40, fat=20, carbohydrate=40, sodium=900),
    dict(name="Cola", price=5, energyKcal=150, protein=0, fat=0, carbohydrate=36, sodium=0),
]


def C(name, p, o=None):
    return {"code": name, "name": name, "price": p, "originalPrice": o or p, "family": family(name), "tags": []}


CANDS = [C("麦辣鸡腿堡两件套", 15, 32), C("巨无霸三件套", 36, 49), C("麦香鱼套餐", 33, 46),
         C("板烧鸡腿堡三件套", 34, 47), C("吉士汉堡包套餐", 26, 38), C("麦乐鸡套餐", 25, 37),
         C("精选单人餐三件套", 34, 46)]


def run(*args):
    import contextlib, io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            rc = cli.main(list(args))
        except SystemExit as e:
            rc = e.code
    return rc, buf.getvalue()


class FitWeek(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); cli.HOME = self.tmp

    def test_optimize_cheapest(self):
        p = optimize(ITEMS, Goal(max_kcal=600, min_protein=35), top=3)
        self.assertEqual(p[0]["total"]["price"], 18)
        for plan in p:
            self.assertGreaterEqual(plan["total"]["protein"], 35)
            self.assertLessEqual(plan["total"]["energyKcal"], 600)

    def test_optimize_bruteforce(self):
        g = Goal(max_kcal=700, min_protein=40, max_items=3)
        best = min((sum(i["price"] for i in c) for k in range(1, 4)
                    for c in itertools.combinations_with_replacement(ITEMS, k)
                    if sum(i["protein"] for i in c) >= 40 and sum(i["energyKcal"] for i in c) <= 700
                    and all(c.count(x) <= 2 for x in c)), default=None)
        self.assertEqual(optimize(ITEMS, g)[0]["total"]["price"], best)

    def test_parse_and_match(self):
        raw = "[2]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:\n  巨无霸,null,2146,513,27,26,42,961,171\n  纯悦,能量约清水1杯,0,0,0,0,0,0,0"
        n = parse_nutrition({"data": raw})
        self.assertEqual(n[0]["protein"], 27)
        idx = nutrition_index([{"name": "可乐中杯"}, {"name": "那么大鸡排"}])
        self.assertTrue(match("可乐", idx)); self.assertTrue(match("那么大鸡排（椒盐风味）", idx))

    def test_plan_week(self):
        p = plan_week(CANDS, 150, 5)
        self.assertEqual(len(p), 5)
        self.assertLessEqual(sum(c["price"] for c in p), 150)
        self.assertEqual(len({c["name"] for c in p}), 5)

    def test_lunch_filter(self):
        meals = {"1": {"name": "巨无霸三件套", "currentPrice": "36"}, "2": {"name": "开心亲子双人餐", "currentPrice": "59"},
                 "3": {"name": "可乐", "currentPrice": "9.5"}}
        self.assertEqual([c["name"] for c in lunch_candidates(meals)], ["巨无霸三件套"])

    def test_fit_cli_offline(self):
        rc, out = run("fit", "--goal", "高蛋白", "--json")
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertTrue(data["plans"])
        self.assertGreaterEqual(data["plans"][0]["total"]["protein"], 40)

    def test_week_cli_offline(self):
        rc, out = run("week", "--budget", "130", "--json")
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertEqual(len(data["plan"]), 5)

    def test_week_dates(self):
        d = cli._week_dates(dt.date(2026, 10, 16), 3)
        self.assertEqual([x.weekday() for x in d], [4, 0, 1])


if __name__ == "__main__":
    unittest.main()
