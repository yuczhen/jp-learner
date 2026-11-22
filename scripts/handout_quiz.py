"""Practice questions taken verbatim from the owner's N3 handouts (question, options and the answer marked
in the handout with a red box). Nothing is written or judged here: the answer is the option inside the red box.
-> data/handout_quiz.json  [{src, sec, no, q, opts, a}]   (a = 1-based option number)"""
import json, re, sys
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parent.parent
N3 = Path("/Users/yuchicheng/Documents/!!各類課程/2026 東吳日文n3")
SRCS = [  # (file, label shown on the page)
    ("文法/W10-1122/N3 [文法と読解] (1)  答案付き.pdf", "N3［文法と読解］(1)"),
    ("文法/W10-1122/N3 [文法と読解] (2)  答案付き.pdf", "N3［文法と読解］(2)"),
]


def red_boxes(page):
    return [d["rect"] for d in page.get_drawings()
            if d.get("color") and d["color"][0] > 0.7 and d["color"][1] < 0.4 and d["color"][2] < 0.4]


def mondai1(doc):
    """問題1 (fill in the blank): question text, 4 options, answer from the red box."""
    text = "".join(p.get_text() for p in doc)
    sec = text.split("問題1", 1)[1].split("問題2", 1)[0]
    sec = re.sub(r"N3 \[文法と読解\] \(\d\)\s*\n", "", sec)               # running page header
    blocks = re.split(r"\n\s*(?=(?:1[0-3]|[1-9])\s{2,})", "\n" + sec)
    qs = []
    for b in blocks:
        m = re.match(r"\s*(\d{1,2})\s{2,}(.*)", b, re.S)
        if not m:
            continue
        no, body = int(m.group(1)), m.group(2)
        k = re.search(r"\n\s*1\.", body)
        q, op = body[:k.start()], body[k.start():]
        op = re.split(r"\n\s*-{5,}", op)[0]                                   # separator line after the last option
        opts = [re.sub(r"\s+", "", o) for o in re.split(r"\s*[1-4]\.\s*", op.strip())[1:]]
        q = re.sub(r"\s*\n\s*", "", q.strip())                                # PDF line wraps are layout only
        q = re.sub(r"(」|[）)])\s*(?=[^\s「」（）()]{1,6}\s?「|[（(])", r"\1\n", q)  # new line per speaker
        q = re.sub(r"（\s*）", "（　　）", q)
        qs.append({"no": no, "q": q, "opts": opts})
    boxes = []                                    # red boxes in reading order, text inside each
    for p in doc:
        words = p.get_text("words")
        for r in red_boxes(p):
            boxes.append("".join(w[4] for w in words if pymupdf.Rect(w[:4]).intersects(r)))
    boxes = boxes[:len(qs)]
    for q, bx in zip(qs, boxes):
        m = re.match(r"（?([1-4])\.(.*)", bx)
        n, t = int(m.group(1)), re.sub(r"\s+", "", m.group(2))
        if q["opts"][n - 1] != t:
            sys.exit(f"answer box does not match option: Q{q['no']} box={bx} opts={q['opts']}")
        q["a"] = n
    return qs


out = []
for f, label in SRCS:
    doc = pymupdf.open(N3 / f)
    qs = mondai1(doc)
    assert [q["no"] for q in qs] == list(range(1, 14)), [q["no"] for q in qs]
    out += [{"src": label, "sec": "問題1", **q} for q in qs]
(ROOT / "data/handout_quiz.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf8")
print(len(out), "questions")
