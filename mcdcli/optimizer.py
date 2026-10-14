"""Exact branch-and-bound search: cheapest McDonald's combo meeting macro goals."""
from dataclasses import dataclass, field

PRESETS = {
    "减脂": dict(max_kcal=550, min_protein=30, max_fat=22),
    "增肌": dict(max_kcal=850, min_protein=45, min_kcal=550),
    "均衡": dict(max_kcal=700, min_protein=25),
    "高蛋白": dict(max_kcal=650, min_protein=40),
}


@dataclass
class Goal:
    max_kcal: float = 600
    min_kcal: float = 0
    min_protein: float = 30
    max_fat: float = 1e9
    max_carb: float = 1e9
    max_sodium: float = 1e9
    budget: float = 1e9
    max_items: int = 4
    max_same: int = 2
    exclude: list = field(default_factory=list)


def _ok_item(it, g):
    return it["energyKcal"] <= g.max_kcal and it.get("price", 0) <= g.budget and not any(x in it["name"] for x in g.exclude)


def optimize(items, goal, top=3, objective="price"):
    """items: dicts with name, price, energyKcal, protein, fat, carbohydrate, sodium.
    objective='price' -> minimise total price; 'protein' -> maximise protein (offline / no prices).
    Returns list of plans sorted best-first."""
    cand = [i for i in items if _ok_item(i, goal)]
    # dominance pruning: drop zero-protein drinks except one free water etc. keep everything; small N anyway
    cand.sort(key=lambda i: -(i["protein"] / max(i.get("price", 1) or 1, 0.1)))
    n = len(cand)
    max_pp = max((i["protein"] / max(i["energyKcal"], 1) for i in cand), default=0)  # protein per kcal bound
    results = []

    def score(tot):
        return (round(tot["price"], 2), -tot["protein"]) if objective == "price" else (-tot["protein"], round(tot["price"], 2))

    def worst():
        return score(results[-1][1]) if len(results) >= top else None

    def rec(start, chosen, tot):
        if tot["protein"] >= goal.min_protein and tot["energyKcal"] >= goal.min_kcal and chosen:
            s = score(tot)
            w = worst()
            if w is None or s < w:
                results.append((list(chosen), dict(tot)))
                results.sort(key=lambda r: score(r[1]))
                del results[top:]
            if objective == "price":
                return  # adding items only raises price
        if len(chosen) >= goal.max_items:
            return
        # bound: remaining kcal can add at most max_pp*kcal protein
        if tot["protein"] + max_pp * (goal.max_kcal - tot["energyKcal"]) < goal.min_protein:
            return
        w = worst()
        for j in range(start, n):
            it = cand[j]
            if chosen.count(j) >= goal.max_same:
                continue
            nt = {k: tot[k] + it.get(k, 0) for k in tot}
            if (nt["energyKcal"] > goal.max_kcal or nt["fat"] > goal.max_fat or nt["carbohydrate"] > goal.max_carb
                    or nt["sodium"] > goal.max_sodium or nt["price"] > goal.budget + 1e-9):
                continue
            if objective == "price" and w is not None and len(results) >= top and nt["price"] > w[0]:
                continue
            chosen.append(j)
            rec(j, chosen, nt)
            chosen.pop()
            w = worst()

    zero = dict(price=0.0, energyKcal=0.0, protein=0.0, fat=0.0, carbohydrate=0.0, sodium=0.0)
    rec(0, [], zero)
    plans = []
    for idxs, tot in results:
        counts = {}
        for j in idxs:
            counts[j] = counts.get(j, 0) + 1
        plans.append({"items": [dict(cand[j], quantity=q) for j, q in counts.items()],
                      "total": {k: round(v, 1) for k, v in tot.items()}})
    return plans
