# Attach sigure "A和B的差別" articles to the batches whose words / grammar they compare.
# Classification only: an article goes to a batch when one of its compared terms is a word or a
# grammar pattern of that batch. Writes data/diff_match.json {"date|slot": [slug, ...]}.
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = json.loads((ROOT / "data/diffs.json").read_text(encoding="utf8"))
plan = json.loads((ROOT / "data/plan.json").read_text(encoding="utf8"))
voc = {v["id"]: v for v in json.loads((ROOT / "data/vocab.json").read_text(encoding="utf8"))}
for v in json.loads((ROOT / "data/vocab_extra.json").read_text(encoding="utf8")):
    voc.setdefault(v["id"], v)
gpath = ROOT / "data/grammar_merged.json"
gram = json.loads((gpath if gpath.exists() else ROOT / "data/grammar.json").read_text(encoding="utf8"))


def norm(s):
    s = re.sub(r"[（(][^）)]*[）)]", "", s or "")
    return s.replace("〜", "").replace("～", "").strip()


def vforms(v):
    return {f for f in (norm(v["word"]), norm(v.get("reading", ""))) if f}


def gforms(g):
    out = set()
    for q in re.findall(r"「([^」]+)」", g.get("title", "")):
        out |= {norm(x) for x in re.split(r"[・、／/]", q) if norm(x)}
    return out


match = {}
for day in plan["days"]:
    for b in day["batches"]:
        forms = set()
        for i in b.get("vocab", []):
            if i in voc:
                forms |= vforms(voc[i])
        for i in b.get("grammar", []):
            if i in gram:
                forms |= gforms(gram[i])
        hit = [s for s, a in D.items() if any(norm(t) in forms for t in a["terms"])]
        if hit:
            match[f'{day["date"]}|{b["slot"]}'] = hit

(ROOT / "data/diff_match.json").write_text(json.dumps(match, ensure_ascii=False, indent=0), encoding="utf8")
used = {s for v in match.values() for s in v}
print(len(match), "batches with comparisons;", len(used), "of", len(D), "articles used")
for k, v in list(match.items())[:60]:
    print(k, [D[s]["title"] for s in v])
