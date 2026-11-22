"""Furigana exactly as printed in the owner's handout PDFs.
Small text (ruby) printed right above kanji is attached to those kanji by position.
-> data/handout_ruby.json  {"pages": [ {"f": file, "p": page, "t": plain text, "r": [[start, end, reading], ...]} ]}
Lookup: find a sentence in "t" and rebuild 漢字(よみ) from the ruby ranges inside it."""
import glob, json, re
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parent.parent
BASE = Path("/Users/yuchicheng/Documents/!!各類課程")
KANJI = re.compile(r"[一-鿿々〆ヶ]")


def page_ruby(page):
    chars, rubies = [], []
    for b in page.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                small = s["size"] < 8.5
                for c in s["chars"]:
                    (rubies if small else chars).append((c["c"], c["bbox"], s["size"]))
    # base text in reading order (by line, then x)
    chars.sort(key=lambda c: (round(c[1][1] / 4), c[1][0]))
    lines, cur, cy = [], [], None
    for c in chars:
        y = (c[1][1] + c[1][3]) / 2
        if cy is not None and abs(y - cy) > c[2] * 0.6:
            lines.append(cur); cur = []
        cur.append(c); cy = y if not cur[:-1] else cy
    if cur:
        lines.append(cur)
    # ruby chars grouped into runs (same baseline, adjacent)
    rubies.sort(key=lambda c: (round(c[1][1]), c[1][0]))
    runs = []
    for c in rubies:
        if runs and abs(runs[-1]["y"] - c[1][1]) < 2 and c[1][0] - runs[-1]["x1"] < c[2] * 0.6:
            runs[-1]["t"] += c[0]; runs[-1]["x1"] = c[1][2]
        else:
            runs.append({"t": c[0], "x0": c[1][0], "x1": c[1][2], "y": c[1][1], "y1": c[1][3]})
    text, ranges, off = "", [], 0
    for ln in lines:
        s = "".join(c[0] for c in ln)
        top = min(c[1][1] for c in ln)
        for r in runs:
            if not re.fullmatch(r"[ぁ-ゖー]+", r["t"]) or not (0 <= top - r["y1"] < 6):
                continue
            idx = [i for i, c in enumerate(ln) if KANJI.match(c[0]) and c[1][2] > r["x0"] + 1 and c[1][0] < r["x1"] - 1]
            if idx and idx == list(range(idx[0], idx[-1] + 1)):
                ranges.append([off + idx[0], off + idx[-1] + 1, r["t"]])
        text += s + "\n"; off += len(s) + 1
    return text, ranges


out = []
for f in sorted(glob.glob(str(BASE / "2026 *" / "**" / "*.pdf"), recursive=True)):
    try:
        doc = pymupdf.open(f)
    except Exception:
        continue
    for i, p in enumerate(doc):
        t, r = page_ruby(p)
        if r:
            out.append({"f": str(Path(f).relative_to(BASE)), "p": i, "t": t, "r": r})
(ROOT / "data/handout_ruby.json").write_text(json.dumps({"pages": out}, ensure_ascii=False), encoding="utf8")
print(len(out), "pages with printed furigana,", sum(len(x["r"]) for x in out), "readings")
