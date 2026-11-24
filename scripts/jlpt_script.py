"""Official JLPT 聴解スクリプト (2012/2018 sample PDFs from the JLPT site) -> per-question script with the printed furigana.
-> data/jlpt_script.json {item id: ["漢字(よみ)…", ...]}"""
import json, re, sys
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import furi
_ns = {"__file__": str(ROOT / "scripts/handout_ruby.py")}
exec((ROOT / "scripts/handout_ruby.py").read_text(encoding="utf8").split("out = []")[0], _ns)

N = lambda t: re.sub(r"[^ぁ-ゖァ-ヺ一-龥々ー]", "", re.sub(r"\([^()]*\)", "", t or ""))


def blocks(year):
    lines = []
    for p in pymupdf.open(ROOT / f"sources/jlpt/{year}_N3script.pdf"):
        t, r = _ns["page_ruby"](p)
        rb = furi.build(t, [tuple(x) for x in r])
        lines += [l.strip() for l in rb.split("\n")]
    out, cur, mon = [], None, ""
    for l in lines:
        pl = re.sub(r"\([^()]*\)", "", l)
        if not pl or re.fullmatch(r"聴解スクリプト|\d+|（Ｍ：男性.*|聴解スクリプト\d*", pl):
            continue
        m = re.fullmatch(r"問題\s*([1-5１-５])", pl)
        if m:
            mon = m.group(1).translate(str.maketrans("１２３４５", "12345")); continue
        if re.fullmatch(r"(\d+|例)\s*番?|[0-9０-９]+\s*番", pl) or pl == "例":
            cur = {"mon": mon, "ban": pl, "lines": []}; out.append(cur); continue
        if cur is None:
            continue
        # speaker turns start with Ｍ/Ｆ/男/女; other lines continue the previous one (PDF wraps)
        if cur["lines"] and not re.match(r"^(Ｍ|Ｆ|Ｆ１|Ｆ２|Ｍ１|Ｍ２|男|女)\s*[：:]", pl) and \
                not re.search(r"[。？！?」]$", re.sub(r"\([^()]*\)", "", cur["lines"][-1])):
            cur["lines"][-1] += l
        else:
            cur["lines"].append(l)
    return out


J = json.loads((ROOT / "data/jlpt.json").read_text(encoding="utf8"))
B = {y: blocks(y) for y in ("2012", "2018")}
res, miss = {}, []
for s in J["sets"]:
    for sec in s["sections"]:
        for it in sec["items"]:
            if not it["id"].startswith("L"):
                continue
            mon = re.search(r"問題\s*(\d)", it["g"]).group(1)
            q = N(it["q"])
            bg = lambda t: {t[i:i + 2] for i in range(len(t) - 1)}
            cand = [b for b in B[it["src"]] if b["mon"] == mon and b["ban"] != "例"]
            # match on the speech-recognition transcript of this clip (whole text), which tells similar questions apart
            w = N("".join(it.get("script") or [])) or q
            sc = sorted(((len(bg(w) & bg(N("".join(b["lines"])))) / max(1, len(bg(w))), i) for i, b in enumerate(cand)), reverse=True)
            if sc and sc[0][0] >= 0.4 and (len(sc) == 1 or sc[0][0] - sc[1][0] >= 0.15):
                res[it["id"]] = cand[sc[0][1]]["lines"]
            else:
                miss.append((it["id"], it["src"], mon, it["q"][:20], [round(x[0], 2) for x in sc[:3]]))
(ROOT / "data/jlpt_script.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf8")
print(len(res), "scripts; missing", miss)
