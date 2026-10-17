"""Build data/plan.json: N days x 2 batches, each = one group of similar grammar
+ vocabulary (words from the grammar's own examples first, then similar-kanji runs)."""
import json, math, re, sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START = date(2026, 10, 16)
EXAM = date(2026, 12, 6)   # JLPT Dec 2026 (please confirm)
TOTAL_DAYS = (EXAM - START).days - 7   # last week = free self-review
# vocab level -> (first batch, last batch+1): keeps word level aligned with grammar progress
WINDOW = {"N5": (0, 40), "N4": (0, 56), "N3": (8, 10**6)}
MAX_G = 5                  # grammar items per batch

# --- curated "similar grammar" groups (N3 grammar numbers) ----------------
N3_GROUPS = [
    ("理由・原因", [4, 33, 34, 119, 116, 139, 85, 61, "c-L5-3", "c-L5-5"]),
    ("對比・相反・代替", [83, 101, 90, 81, 130, 14, 78]),
    ("逆接・讓步・反而", [18, 20, 37, 63, 62, 6, 72, "c-L8-5"]),
    ("添加・強調・例示", [98, 100, 30, 21, 35, 109, 76]),
    ("變化・伴隨・隨著", [2, 82, 86, 88, 71, 70, 39, 27]),
    ("時間・同時・順序", ["c-L1-2", 3, 28, 29, 67, 41, 47, 48, 102, 16, 66]),
    ("推測・必然・傳聞", [10, 5, 80, 84, 99, 126, 127, 128, 60, 138, 43, "c-L7-2", "c-L7-5", "c-L8-2"]),
    ("應該・義務・只能・不可能", [23, 24, 104, 107, 124, 121, 120, 117, 118, 129, "c-L10-1", "c-L10-4"]),
    ("假定・條件", [69, 122, 59, 97, 96, 125, 75, 89, 106, "c-L6-2", "c-L6-5"]),
    ("範圍・對象・立場・依據", [11, 77, 79, 87, 68, 91, 92, 93, 133, 134, 135, 136, 131, 113, 114, 105, 64]),
    ("狀態・樣子・傾向", [7, 8, 15, 17, 40, 44, 45, 110, 103, 132, 112, 111]),
    ("程度・最上級・與其…不如", [19, "c-L3-4"]),
    ("授受・請求・希望・使役", [31, 32, 49, 50, 53, 55, 56, 57, 36, 94, 95, 137, 140, 25, 26, 38]),
]
N4_EXTRA = ("N4 補充（必須・不必・預定・請求）", ["c-N4-1", "c-N4-2", "c-N4-3", "c-N4-4"])
KEIGO_GROUP = ("敬語（尊敬語・謙譲語・丁寧語）", ["c-K-1", "c-K-2", "c-K-3", "c-K-4", "c-K-5"])
N5_GROUPS = [("N5 名詞", range(0, 7)), ("N5 い形容詞", range(7, 12)), ("N5 な形容詞", range(12, 17)),
             ("N5 動詞", range(17, 25)), ("N5 助詞", range(25, 35)), ("N5 表現", range(35, 45)),
             ("N5 副詞・接續・助動詞", range(45, 51))]
N4_GROUPS = [("N4 變化・基本表現", range(1, 10)), ("N4 假定條件(と/ば/たら/なら)", range(10, 14)),
             ("N4 使役・受身", range(14, 16)), ("N4 補助動詞(ていく/てくる…)", range(16, 21)),
             ("N4 推量・樣態(そうだ/らしい/ようだ)", range(21, 28)), ("N4 授受・敬語", range(28, 31)),
             ("N4 意志・目的・用法", range(31, 45)), ("N4 禁止許可・助詞・副詞", range(45, 54))]


def chunk(ids, max_n=MAX_G):
    n = math.ceil(len(ids) / max_n)
    size = len(ids) / n
    return [ids[round(i * size):round((i + 1) * size)] for i in range(n)]


def base(w):
    return re.sub(r"[（(][^）)]*[）)]|[～〜]", "", w).strip()


def kanji_key(w):
    b = base(w)
    m = re.search(r"[一-鿿]", b)
    return (0, m.group(0)) if m else (1, b[-2:] if re.search(r"[ァ-ヶ]", b) is None else "ｱ" + b[:1])


def main():
    gp = ROOT / "data/grammar_merged.json"
    g = json.loads((gp if gp.exists() else ROOT / "data/grammar.json").read_text(encoding="utf8"))
    v = json.loads((ROOT / "data/vocab.json").read_text(encoding="utf8"))
    for k in g:                                  # fall back to title for missing meaning
        if not g[k]["meaning"]:
            g[k]["meaning"] = re.sub(r"^.*?」", "", g[k]["title"]).strip()

    def gid(level, n):
        return n if isinstance(n, str) else f"{level}-{n:02d}"

    # ---- grammar schedule --------------------------------------------------------------
    # 1) days already sent stay exactly as they were (data/plan_frozen.json)
    # 2) the rest is grouped by *topic family* across levels (N5/N4/N3 together, like the comparison tables)
    # 3) leftover basics (tutorial-style N5/N4 items, remaining N3 groups) are woven in proportionally
    frozen = json.loads((ROOT / "data/plan_frozen.json").read_text(encoding="utf8")) if (ROOT / "data/plan_frozen.json").exists() else []
    assigned = {x for f in frozen for x in f["grammar"]}
    LV = {"N5": 0, "N4": 1, "N3": 2}

    def level_of(i):
        if i.startswith("c-N4"):
            return "N4"
        return "N3" if i.startswith("c-") else g[i]["level"]

    def order_key(i):
        return (LV[level_of(i)], i)

    FAMILY_ORDER = ["C01", "C13", "C14", "C03", "C16", "C17", "KEIGO", "C02", "C05", "C06", "C04", "C09", "C10",
                    "C11", "C12", "C07", "C08", "C15", "C18", "C19", "C20", "C21", "C22", "C23", "C24", "C25", "C26"]
    fams = {f["id"]: f for f in json.loads((ROOT / "data/compare.json").read_text(encoding="utf8"))}
    fam_units = []
    for fid in FAMILY_ORDER:
        if fid == "KEIGO":
            name, items = KEIGO_GROUP[0], [x for x in KEIGO_GROUP[1] if x in g and x not in assigned]
        else:
            f = fams.get(fid)
            if not f:
                continue
            name = f["title"]
            items = sorted([m for m in f["members"] if m in g and m not in assigned], key=order_key)
        if items:
            fam_units.append((name, items))
            assigned.update(items)
    left = {"N5": [], "N4": [], "N3": []}
    for name, nums in N5_GROUPS:
        left["N5"].append((name, [gid("n5", n) for n in nums]))
    for name, nums in N4_GROUPS:
        left["N4"].append((name, [gid("n4", n) for n in nums]))
    left["N4"].append((N4_EXTRA[0], list(N4_EXTRA[1])))
    for name, nums in N3_GROUPS:
        left["N3"].append((name, [gid("n3", n) for n in nums]))
    queues_g = {"F": [], "N5": [], "N4": [], "N3": []}
    for name, items in fam_units:
        for part in chunk(items):
            queues_g["F"].append({"theme": name, "grammar": part})
    for lv in ("N5", "N4", "N3"):
        for name, ids in left[lv]:
            ids = [x for x in ids if x in g and x not in assigned]
            assigned.update(ids)
            for part in (chunk(ids) if ids else []):
                queues_g[lv].append({"theme": name, "grammar": part})
    rest = sorted([k for k in g if k not in assigned], key=order_key)
    for part in (chunk(rest) if rest else []):
        queues_g["N3"].append({"theme": "N3 其他", "grammar": part})
    SPAN = {"F": 1.0, "N3": 1.0, "N4": 0.8, "N5": 0.55}          # basics are woven into the first part of the schedule
    scored = []
    for key, q in queues_g.items():
        for i, b in enumerate(q):
            scored.append(((i + 0.5) / len(q) * SPAN[key], {"F": 0, "N3": 1, "N4": 2, "N5": 3}[key], b))
    scored.sort(key=lambda t: (t[0], t[1]))
    batches = [dict(f) for f in frozen] + [b for _, _, b in scored]
    B = len(batches)

    # vocab queues per level, similar kanji adjacent
    queues = {}
    for lv in ("N5", "N4", "N3"):
        ws = [e for e in v if e["level"] == lv]
        ws.sort(key=lambda e: (kanji_key(e["word"]), e["reading"]))
        queues[lv] = ws
    byid = {e["id"]: e for e in v}
    taken = set()

    def examples_text(b):
        return "".join(ex["ja"] for gi in b["grammar"]
                       for ex in g[gi]["examples"] + [e for c in g[gi].get("class", []) for e in c["examples"]])

    for i, b in enumerate(batches):
        txt = examples_text(b)
        pair = []
        for e in v:
            if e["id"] in taken:
                continue
            bw = base(e["word"])
            if len(bw) >= 2 and re.search(r"[一-鿿]", bw) or len(bw) >= 4:
                if bw in txt:
                    pair.append(e["id"])
        pair = pair[:8]
        taken.update(pair)
        words = list(pair)
        for lv in ("N3", "N4", "N5"):
            a, z = WINDOW[lv]
            z = min(z, B)
            q = [e for e in queues[lv] if e["id"] not in taken]
            queues[lv] = q
            if i < a or not q:
                continue
            n = math.ceil(len(q) / max(1, z - i))
            take = q[:n]
            words += [e["id"] for e in take]
            taken.update(e["id"] for e in take)
        b["vocab"] = words
        b["n_paired"] = len(pair)
    lp = ROOT / "data/listening.json"                 # listening practice: one clip per batch
    if lp.exists():
        L = json.loads(lp.read_text(encoding="utf8"))
        for k, it in enumerate(L):
            idx = k if len(L) <= 8 else round(k * (B - 1) / max(1, len(L) - 1))
            batches[min(idx, B - 1)]["listen"] = it["id"]
        placed = {b.get("listen") for b in batches}
        spare = [it["id"] for it in L if it["id"] not in placed]      # more clips than batches -> use them on review days
    # review (titles of grammar from 2 batches earlier)
    for i, b in enumerate(batches):
        b["review"] = batches[i - 2]["grammar"] if i >= 2 else []

    days = []
    nlearn = math.ceil(B / 2)
    for d in range(TOTAL_DAYS):
        day = {"day": d + 1, "date": (START + timedelta(d)).isoformat(), "batches": []}
        for s, slot in enumerate(("am", "pm")):
            idx = d * 2 + s
            if idx < B:
                bb = dict(batches[idx]); bb["slot"] = slot; bb["kind"] = "learn"
                day["batches"].append(bb)
        days.append(day)
    # review days: each one replays a single earlier study day (am + pm), so the day keeps one voice
    for rd, day in enumerate(days[nlearn:]):
        j = (rd * 7 + 3) % max(1, nlearn)
        for si, slot in enumerate(("am", "pm")):
            src = batches[min(B - 1, j * 2 + si)]
            rb = {"slot": slot, "kind": "review", "theme": "複習・" + src["theme"],
                  "grammar": src["grammar"], "vocab": src["vocab"][:18], "review": []}
            if "spare" in dir() and spare:
                rb["listen"] = spare.pop(0)
            day["batches"].append(rb)
    plan = {"start": START.isoformat(), "exam": EXAM.isoformat(), "learn_days": nlearn,
            "total_days": TOTAL_DAYS, "batches": B, "days": days}
    (ROOT / "data/plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf8")
    allv = {i for b in batches for i in b["vocab"]}
    print(f"batches={B} learn_days={nlearn} total_days={TOTAL_DAYS}")
    print(f"grammar covered={sum(len(b['grammar']) for b in batches)}/{len(g)}  vocab covered={len(allv)}/{len(v)}")
    sizes = [len(b['vocab']) for b in batches]
    print("vocab/batch min/avg/max", min(sizes), sum(sizes) // B, max(sizes), " paired total", sum(b['n_paired'] for b in batches))


if __name__ == "__main__":
    main()
