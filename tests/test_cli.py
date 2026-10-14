import contextlib, io, json, os, re, tempfile, unittest

os.environ["MCD_OFFLINE"] = "1"
os.environ["NO_COLOR"] = "1"
from mcdcli import cli
from mcdcli.backend import Live, READ_ONLY_TOOLS
from mcdcli.data import nutrition_index

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(*args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            rc = cli.main(list(args))
        except SystemExit as e:
            rc = e.code
    return rc, buf.getvalue()


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); cli.HOME = self.tmp

    def test_flow_install_ls_checkout(self):
        self.assertEqual(run("install", "板烧鸡腿堡", "可乐@2")[0], 0)
        rc, out = run("price", "add", "苹果片")
        self.assertIn("苹果片", out)
        rc, out = run("ls"); self.assertIn("可乐@9900008751 ×2", out)
        rc, out = run("checkout", "--dry-run")
        self.assertEqual(rc, 0); self.assertIn("TOTAL    ¥49.50", out); self.assertIn("0 orders created", out)

    def test_real_checkout_refused(self):
        run("install", "巨无霸")
        rc, out = run("checkout")
        self.assertEqual(rc, 2); self.assertIn("refusing", out)

    def test_read_only_guard(self):
        for bad in ("create-order", "cancel-order", "auto-bind-coupons", "draw-lottery", "mall-create-order"):
            self.assertNotIn(bad, READ_ONLY_TOOLS)
        live = Live.__new__(Live)
        with self.assertRaises(AssertionError):
            live.call("create-order", {})

    def test_menu_grep(self):
        rc, out = run("menu", "--grep", "板烧")
        self.assertTrue(out.strip()) ; self.assertTrue(all("板烧" in l for l in out.strip().splitlines()))

    def test_404(self):
        rc, out = run("install", "不存在的汉堡")
        self.assertNotEqual(rc, 0)

    def test_audit(self):
        idx = nutrition_index(json.load(open(os.path.join(ROOT, "data", "nutrition.json"))))
        tot, issues, unknown = cli.audit([{"name": "巨无霸", "qty": 2, "code": "1100"}, {"name": "可乐", "qty": 1, "code": "x"}], idx)
        self.assertEqual(tot["energyKcal"], 513 * 2 + 147)
        self.assertIn("high", [s for s, _, _ in issues])

    def test_rm_and_nutrition_coupon_cal(self):
        run("install", "麦香鱼"); run("rm", "麦香鱼")
        self.assertIn("(empty)", run("ls")[1])
        self.assertIn("巨无霸", run("nutrition", "巨无霸")[1])
        self.assertIn("CAN_GET", run("coupon", "ls")[1])
        self.assertEqual(run("cal")[0], 0)

    def test_no_secret(self):
        for d, _, fs in os.walk(ROOT):
            if ".git" in d: continue
            for f in fs:
                if f.endswith((".py", ".md", ".json")):
                    self.assertNotRegex(open(os.path.join(d, f), encoding="utf-8").read(), r"Bearer [A-Za-z0-9]{20,}")
