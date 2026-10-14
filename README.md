<h1 align="center">🍔⌨️ mcd-cli</h1>
<p align="center"><b><code>npm install</code> 你的午饭。把麦当劳装进 $PATH。</b></p>
<p align="center">
  <img src="https://img.shields.io/badge/McDonald's-MCP-FFC72C?logo=mcdonalds&logoColor=DA291C" />
  <img src="https://img.shields.io/badge/version-10.24.0-orange" />
  <img src="https://img.shields.io/badge/orders%20created-0-brightgreen" />
  <img src="https://img.shields.io/badge/vulnerabilities-2%20(sodium)-yellow" />
  <img src="https://img.shields.io/badge/license-MIT-green" />
</p>

```text
$ mcd install 板烧鸡腿堡 薄皮焦香V翅 可乐
+ 板烧鸡腿堡@1406 ×1  ¥23.5
+ 薄皮焦香V翅@520445 ×1  ¥16
+ 可乐@9900008751 ×1  ¥9.5

added 3 packages, and audited 3 packages in 3.6s
run `mcd audit` for details · `mcd checkout --dry-run` to build

$ mcd audit
# mcd audit report

moderate 钠 1635mg，约占每日建议量 82%
         fix: 饮品换成无糖/纯悦
low      含糖饮品/甜品: 可乐
         fix: 试试无糖可口可乐或纯悦

总计 762 kcal · 蛋白 40g · 脂肪 28g · 碳水 84g · 钠 1635mg
found 2 vulnerabilities (moderate, low)

$ mcd checkout --dry-run
> mcd@10.24.0 build --dry-run
> calculate-price --store 1450713

  ✓ 板烧鸡腿堡                ×1  ¥23.50
  ✓ 薄皮焦香V翅               ×1  ¥16.00
  ✓ 可乐                   ×1  ¥9.50

  TOTAL    ¥49.00  (live: calculate-price)

Build succeeded in 2.0s · 0 orders created · 0 yuan spent

$ mcd fit --goal 高蛋白
🍔 mcd fit | 数据: 本地快照 | 门店: 麦当劳上海黄浦华旭国际大厦餐厅
目标: ≤650kcal, 蛋白≥40g

方案 1  ¥30.0
  - 那么大鸡排（椒盐风味）  ¥14.0  385kcal  蛋白24g
  - 薄皮焦香V翅  ¥16.0  192kcal  蛋白17g
  合计: 577 kcal | 蛋白质 41g | 脂肪 32g | 碳水 30g | 钠 1590mg

$ mcd week --budget 130
💼 mcd week | 数据: 本地快照 | 门店: 麦当劳上海黄浦华旭国际大厦餐厅
预算 ¥130 / 5 天（日均 ¥26.0）
…一周午餐不重样，合计约 ¥128.7，比单点原价省近百元
```
<sub>以上为 2026-10-14 调用麦当劳官方 MCP 的真实/快照输出（上海人民广场附近门店）。</sub>

## ✨ 亮点
- 📦 **npm 手感**：`install / rm / ls / audit`，`可乐@2` 表示两杯
- 🛡️ **`mcd audit`**：用官方营养数据扫描这一餐的"漏洞"（钠超标、热量过高、蛋白不足、含糖饮品），每条都附 fix 建议
- 💪 **`mcd fit`**：麦门健身餐——按热量/蛋白质目标做精确搜索，算出最便宜组合（减脂/增肌/高蛋白/均衡预设）
- 💼 **`mcd week`**：打工人周预算——一周午餐不重样，卡总预算、换蛋白家族、贴活动日历
- 🧾 **`checkout --dry-run`**：用 `calculate-price` 算出真实应付价，**0 orders created**
- 🔒 **零写操作**：代码里有只读白名单，`create-order` 被硬拒绝；真要下单只能在 Skill 里由你明确回复「确认下单」
- 🐧 **Unix 友好**：`mcd menu | grep 鸡`、`mcd cal`、`NO_COLOR=1`
- 🥚 **彩蛋**：`mcd sudo make me a burger`、`mcd fortune`

## 🚀 安装
```bash
git clone https://github.com/frankxzx/mcd-cli && cd mcd-cli
export PATH="$PWD/bin:$PATH"
export MCD_MCP_TOKEN=你的token     # open.mcd.cn/mcp 获取，切勿提交
mcd store search 上海 人民广场 && mcd store use 1450713
# 没有 Token？先离线试玩：
MCD_OFFLINE=1 mcd install 巨无霸 && MCD_OFFLINE=1 mcd checkout --dry-run
MCD_OFFLINE=1 mcd fit --goal 高蛋白
MCD_OFFLINE=1 mcd week --budget 130
```

作为 AI Skill 使用：
- **Claude Code**：`claude mcp add --transport http mcd-mcp https://mcp.mcd.cn --header "Authorization: Bearer $MCD_MCP_TOKEN"`，把仓库克隆到 `~/.claude/skills/mcd-cli`
- **Cursor**：把 `mcp-config.example.json` 合并进 `~/.cursor/mcp.json`，再把 `SKILL.md` 放到 `.cursor/rules/`
- **WorkBuddy**：连接器 → 自定义连接器 → 配置MCP，粘贴 `mcp-config.example.json`；在技能里导入 `SKILL.md`

然后直接说：「mcd install 一个巨无霸和一杯无糖可乐，再 audit 一下」或「帮我 fit 一顿高蛋白」「这周 130 块怎么排午餐」。

## 📖 命令
| 命令 | 说明 |
|---|---|
| `mcd store search <城市> <关键词>` / `use <code>` | 找门店 / 切换门店 |
| `mcd menu [--grep X] [-c 分类]` | 菜单 |
| `mcd install <餐品>[@数量]…`（`i`/`add`/`price add`） | 加入购物车 |
| `mcd ls` / `mcd rm <餐品>` | 依赖树 / 移除 |
| `mcd nutrition [餐品]` | 营养成分（不带参数时显示购物车） |
| `mcd audit` | 营养安全审计（有 high 级别问题时退出码为 1） |
| `mcd fit [--goal 减脂\|增肌\|高蛋白\|均衡]` | 麦门健身餐：按目标找最便宜组合 |
| `mcd week --budget N [--days 5]` | 打工人周预算：一周午餐不重样 |
| `mcd coupon ls` | 可领 / 可用券（只读） |
| `mcd cal` | 活动日历 |
| `mcd checkout --dry-run`（`build`） | calculate-price 小票 |

### `mcd fit` 常用参数
`--max-kcal` / `--min-protein` / `--max-fat` / `--budget` / `--exclude 鱼,咖啡` / `--city` `--keyword` / `--verify`（用 calculate-price 校验方案 1）

### `mcd week` 常用参数
`--prefer 鸡,牛` / `--exclude 鱼,辣` / `--max-same 2` / `--member`（含麦金卡专享价）

## 🆚 和 mcd-git 有什么不同？
mcd-git 是 git 流派（rebase 凑券、push 下单、贡献图），很好玩。mcd-cli 走**包管理器 + Unix 流派**，主打 `audit` 营养审计、`fit`/`week` 规划，以及永不下单的 dry-run。两个都可以装，`git mcd` 和 `mcd` 不冲突。

## 👥 适合谁
程序员、终端重度用户、健身期还想吃麦当劳的人、想规划一周午餐预算的打工人，以及想研究 MCP 怎么接入的开发者（客户端约 60 行，标准库实现）。

## ✅ 测试
```bash
python3 -m unittest discover -s tests -t .   # 离线运行，从不调用 create-order
```

## ⚠️ 声明
麦当劳程序员创意开发大赛参赛作品，由参赛者独立开发，非麦当劳官方产品。营养与价格仅供参考，以麦当劳官方渠道为准。详见 [CONTEST_DECLARATION.md](./CONTEST_DECLARATION.md)。觉得好玩就 ⭐ 一下。

License: [MIT](./LICENSE)
