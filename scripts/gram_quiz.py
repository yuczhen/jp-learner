# 相似文法練習: for each compare.json family, blank the keyword sigure marks in a member's own example
# (data/raw/n?_??.html). Options = that member's pattern + other members of the same family whose
# sigure title meanings do NOT overlap with it (so the sigure translation shown decides the answer).
# Nothing is written by hand: sentence, keyword, translation and option labels all come from sigure.
import json, re, html as H
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = json.loads((ROOT / "data/compare.json").read_text(encoding="utf8"))
G = json.loads((ROOT / "data/grammar.json").read_text(encoding="utf8"))
PER_MEMBER, MAX_OPTS = 3, 4


def text(fr):
    fr = re.sub(r"<rt>.*?</rt>|<rp>.*?</rp>", "", fr, flags=re.S)
    return H.unescape(re.sub(r"<[^>]+>", "", fr)).strip()


def keep(fr):  # same whitelist as the 差別 articles: ruby + keyword span only
    fr = re.sub(r"<button.*?</button>", "", fr, flags=re.S)
    fr = re.sub(r'<span class="keyword">', "\x00", fr)
    fr = re.sub(r"<(?!/?(ruby|rt|rp)\b)[^>]+>", "", fr)
    return fr.replace("\x00", '<span class="keyword">').replace("\x01", "</span>")


def term_gloss(title):
    q = re.findall(r"「([^」]+)」", title)
    gloss = re.sub(r"^.*」", "", title).strip()
    return (q[0] if q else ""), gloss


def bigrams(s):
    s = re.sub(r"[^一-鿿]", " ", s)
    return {w[i:i + 2] for w in s.split() for i in range(len(w) - 1)} | {w for w in s.split() if len(w) == 1}


def kw_ok(t, k):
    t = re.sub(r"[〜～（）()]", "", t)
    return bool(t) and (k == t or t in k or (len(k) >= 2 and k in t) or (len(t) >= 3 and k.startswith(t[:-1])))


def examples(gid):
    f = ROOT / "data/raw" / (gid.replace("-", "_") + ".html")
    if not f.exists():
        return []
    h = f.read_text(encoding="utf8")
    c = re.search(r'<section class="article__content prose">(.*?)</section>', h, re.S)
    out = []
    for li in re.findall(r"<li>(.*?)</li>", c.group(1) if c else "", re.S):
        m = re.search(r'<span lang="ja">(.*)</span>\s*(?:<button[^>]*></button>)?\s*<br>\s*<span class="trans">(.*?)</span>', li, re.S)
        if not m:
            continue
        ja = m.group(1)
        # mark the end of the keyword span so keep() can rebuild it
        ks = re.findall(r'<span class="keyword">(.*?)</span>', ja, re.S)
        if len(ks) != 1:
            continue
        ja = re.sub(r'(<span class="keyword">)(.*?)</span>', lambda x: x.group(1) + x.group(2) + "\x01", ja, count=1, flags=re.S)
        out.append({"ja": keep(ja), "kw": text(ks[0]), "zh": text(m.group(2))})
    return out


quiz = []
for fam in C:
    mem = []
    for gid in dict.fromkeys(fam["members"]):
        if gid in G:
            t, gl = term_gloss(G[gid]["title"])
            if t:
                mem.append((gid, t, gl))
    for gid, t, gl in mem:
        others = [(g2, t2) for g2, t2, gl2 in mem
                  if g2 != gid and t2 != t and gl and gl2 and not (bigrams(gl) & bigrams(gl2))]
        if not others:
            continue
        n = 0
        for ex in examples(gid):
            if n >= PER_MEMBER or not kw_ok(t, ex["kw"]) or not ex["zh"]:
                continue
            opts = list(dict.fromkeys([t] + [t2 for _, t2 in others]))[:MAX_OPTS]
            opts = sorted(opts, key=lambda o: [x[1] for x in mem].index(o))   # family order, answer not always first
            q = re.sub(r'<span class="keyword">.*?</span>', '<span class="blank">（　　）</span>', ex["ja"], count=1, flags=re.S)
            quiz.append({"fam": fam["id"], "gid": gid, "q": q, "full": ex["ja"], "opts": opts, "a": t, "zh": ex["zh"]})
            n += 1

(ROOT / "data/gram_quiz.json").write_text(json.dumps(quiz, ensure_ascii=False), encoding="utf8")
print(len(quiz), "items from", len({q["fam"] for q in quiz}), "families,", len({q["gid"] for q in quiz}), "patterns")
