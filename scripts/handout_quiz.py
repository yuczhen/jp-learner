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


def mondai2(doc):
    """問題2 (★ ordering): question, 4 pieces; order from the red digits written on the blanks; ★ = the digit at ★."""
    text = "".join(p.get_text() for p in doc)
    sec = text.split("問題2", 1)[1].split("問題3", 1)[0]
    sec = re.sub(r"N3 \[文法と読解\] \(\d\)\s*\n", "", sec)
    sec = re.sub(r"\n[ \t]*\d[ \t]*(?=\n)", "\n", sec)                       # stray red digits in the text layer
    qs = []
    for m in re.finditer(r"\n\s*(1[4-8])\s+(.*?)(?=\n\s*1[4-8]\s|\Z)", "\n" + sec, re.S):
        no, body = int(m.group(1)), m.group(2)
        body = re.split(r"\n\s*-{5,}", body)[0]
        k = re.search(r"\n\s*1\.\s", body)
        q, op = body[:k.start()], body[k.start():]
        opts = [re.sub(r"\s+", "", o) for o in re.split(r"\s*[1-4]\.\s*", op.strip())[1:]]
        q = re.sub(r"[ \t\u3000]*\n[ \t\u3000]*", "", q.strip())
        q = re.sub(r"(」|[）)])\s*(?=[^\s「」（）()]{1,6}\s?「|[（(])", r"\1\n", q)
        q = re.sub(r"[ \t\u3000]{2,}", " ", q)
        qs.append({"no": no, "q": q, "opts": opts})
    # red digits and ★ positions, page by page, in reading order of the questions
    rows = []
    for p in doc:
        stars, digits = [], []
        for b in p.get_text("rawdict")["blocks"]:
            for l in b.get("lines", []):
                for sp in l["spans"]:
                    for c in sp["chars"]:
                        if c["c"] == "★":
                            stars.append(c["bbox"])
                        elif c["c"] in "1234" and sp["color"] != 0:
                            digits.append((int(c["c"]), c["bbox"]))
        for st in sorted(stars, key=lambda r: r[1]):
            near = [(d, bb) for d, bb in digits if abs((bb[1] + bb[3]) / 2 - (st[1] + st[3]) / 2) < 25]
            if not near:
                continue
            sy, sx = (st[1] + st[3]) / 2, (st[0] + st[2]) / 2
            if len(near) == 4:                             # the digit written at ★ (on or under it)
                star = min(near, key=lambda n: abs((n[1][0] + n[1][2]) / 2 - sx))[0]
            elif len(near) == 3:                           # nothing written at ★: the number not used elsewhere
                star = ({1, 2, 3, 4} - {d for d, _ in near}).pop()
            else:
                continue
            row = lambda bb: 0 if abs((bb[1] + bb[3]) / 2 - sy) < 9 else (1 if (bb[1] + bb[3]) / 2 > sy else -1)
            order = sorted([((row(bb), bb[0]), d) for d, bb in near if d != star] + [((0, sx), star)])
            rows.append({"star": star, "order": [d for _, d in order]})
            continue
            rows.append({"star": star[0], "order": [d for _, d in order]})
    if len(rows) != len(qs) or any(sorted(r["order"]) != [1, 2, 3, 4] for r in rows):
        sys.exit(f"問題2 answers not read cleanly: {rows}")
    for q, r in zip(qs, rows):
        q["a"], q["order"] = r["star"], r["order"]
        k = r["order"].index(r["star"])                    # blanks are drawn lines in the PDF: put them back
        slots = " ".join(["＿＿＿"] * k + ["＿★＿"] + ["＿＿＿"] * (3 - k))
        q["q"] = re.sub(r"[ \u3000]*★[ \u3000]*", " " + slots + " ", q["q"], count=1)
    return qs


def join_wraps(lines):
    out = []
    for l in lines:
        l = l.rstrip()
        if not l.strip():
            continue
        if out and len(out[-1]) >= 15 and not re.search(r"[。」）)？?！!]\s*$", out[-1]) and not re.match(r"\s*([●■◆①②③④⑤]|\(\d\)|（\d）|[1-4][\.．])", l):
            out[-1] = out[-1].rstrip() + l.strip()
        else:
            out.append(l.strip())
    return out


def reading(doc):
    """問題3 (cloze in a passage, 19-23) and 問題4-7 (passage + questions 24-39); answers = red boxes after 問題1/2."""
    text = "".join(p.get_text() for p in doc)
    sec = "問題3" + text.split("問題3", 1)[1]
    sec = re.sub(r"N3 \[文法と読解\] \(\d\)\s*\n", "", sec)
    sec = re.sub(r"(?m)^[ \t]*\d[ \t]*\n", "", sec)                              # red digits of 問題2 in the text layer
    boxes = []
    for p in doc:
        words = p.get_text("words")
        for r in sorted(red_boxes(p), key=lambda r: (round(r.y0), r.x0)):
            boxes.append("".join(w[4] for w in words if pymupdf.Rect(w[:4]).intersects(r)))
    boxes = boxes[13:]                                                     # first 13 = 問題1
    passages, qs = [], []
    # 問題3: cloze
    c = sec.split("問題4", 1)[0]
    c = re.split(r"\n\s*-{5,}", c)[0]
    lines = re.sub(r"（\s*1\.[^）]*）", lambda m: re.sub(r"\s*\n\s*", " ", m.group(0)), c).split("\n")[1:]
    plines, cq = [], []
    for l in join_wraps(lines):
        m = re.fullmatch(r"（\s*1\.(.*)）\s*", l)
        if m:
            opts = [re.sub(r"\s+", "", o) for o in re.split(r"\s*[1-4]\.\s*", "1." + m.group(1))[1:]]
            cq[-1]["opts"] = opts
            continue
        plines.append(l)
        for n in re.findall(r"（\s*(\d{2})\s*）", l):
            cq.append({"no": int(n)})
    passages.append("\n".join(plines))
    for q in cq:
        q.update({"sec": "問題3", "q": f"（ {q['no']} ）", "pid": 0})
    qs += cq
    # 問題4-7
    rest = "問題4" + sec.split("問題4", 1)[1]
    head = ""
    for ch in re.split(r"\n\s*-{5,}[ \t]*", rest):
        ch = ch.strip("\n")
        m = re.match(r"\s*(問題\d)", ch)
        if m:
            head = m.group(1)
        qm = re.match(r"\s*(\d{2})\s+(.*)", ch, re.S)
        if qm and 24 <= int(qm.group(1)) <= 45:
            body = qm.group(2)
            k = re.search(r"\n\s*1[\.．]", body)
            qt = "\n".join(join_wraps(body[:k.start()].split("\n")))
            ol = join_wraps(re.split(r"\n", body[k.start():]))
            ops = re.split(r"\s*(?:^|\s)[1-4][\.．]\s*", " " + " ".join(ol))
            ops = [o.strip() for o in ops if o.strip()]
            extra = ""
            m4 = re.match(r"^([①-⑳➀-➉])\s+(.+)$", ops[-1], re.S) if ops else None
            if m4:                                                         # table printed right after option ④
                ops[-1] = m4.group(1); extra = m4.group(2)
            if len(ops) > 4:                                               # e.g. a table printed after the options
                extra = "\n".join(ops[4:]); ops = ops[:4]
            qs.append({"sec": head, "no": int(qm.group(1)), "q": qt, "opts": ops, "pid": len(passages) - 1})
            if extra:
                passages[-1] += "\n" + re.sub(r"\s+(?=[●①②➁③④])", "\n", extra)
        else:
            lines = join_wraps(re.sub(r"^\s*問題\d[^\n]*\n?", "", ch).split("\n"))
            if lines:
                passages.append("\n".join(lines))
    if len(boxes) < len(qs):
        sys.exit(f"reading: {len(boxes)} boxes for {len(qs)} questions")
    for q, bx in zip(qs, boxes):
        m = re.match(r"（?\s*([1-4])[\.．]", bx)
        q["a"] = int(m.group(1))
        if len(q.get("opts", [])) != 4:
            sys.exit(f"reading Q{q['no']}: options {q.get('opts')}")
    return passages, qs


# ---- N3衝刺 11/22: 解析 (question with the answer in brackets, teacher's translation, option notes, ポイント)
import importlib.util
_sp = importlib.util.spec_from_file_location("hr", ROOT / "scripts/handout_ruby.py")
_src = (ROOT / "scripts/handout_ruby.py").read_text(encoding="utf8").split("out = []")[0]
_ns = {"__file__": str(ROOT / "scripts/handout_ruby.py")}
exec(_src, _ns)
page_text = lambda f: "".join(_ns["page_ruby"](p)[0] for p in pymupdf.open(N3 / f))   # base text, no furigana
FW = str.maketrans("０１２３４５６７８９", "0123456789")
OPT = re.compile(r"^\s*[１-４1-4][\s．.]")
KANA = re.compile(r"[ぁ-ゖァ-ヺ]")
N = lambda t: re.sub(r"[\s　⤴]", "", t)


def kaiseki1(files):
    text = "\n".join(page_text(f) for f in files)
    parts = re.split(r"(?m)^\s*([０-９]{1,2})．", text)
    blocks = [("１", re.sub(r"^\s*１\s*", "", parts[0]))] + list(zip(parts[1::2], parts[2::2]))
    qs = []
    for no, body in blocks:
        no = int(no.translate(FW))
        lines = [l.rstrip() for l in body.split("\n")]
        k = next(i for i, l in enumerate(lines) if OPT.match(l))
        ql = [l.strip() for l in lines[:k] if l.strip() and KANA.search(l)]
        opts, rest = [], lines[k:]
        for l in rest:
            if not OPT.match(l) or len(opts) == 4:
                if len(opts) == 4:
                    break
                continue
            for m in re.finditer(r"(?:^|\s)([１-４1-4])[\s．.]\s*(\S+)", l):
                if int(m.group(1).translate(FW)) == len(opts) + 1:
                    opts.append(m.group(2))
        jl = []                                              # PDF line wraps: join unless the line ended
        for l in ql:
            if jl and not re.search(r"[」。？?）)]$", jl[-1]) and not re.match(r"^[^「」（）]{1,6}\s*[「：:]", l):
                jl[-1] += l
            else:
                jl.append(l)
        q = "\n".join(jl)
        hit = None
        for m in re.finditer(r"（([^（）]*)）", q):
            if N(m.group(1)) in [N(o) for o in opts]:
                hit = m
        if not hit or len(opts) != 4:
            sys.exit(f"解析 Q{no}: answer/options not found: {q} {opts}")
        a = [N(o) for o in opts].index(N(hit.group(1))) + 1
        qq = q[:hit.start()] + "（　　）" + q[hit.end():]
        exp = "\n".join(l for l in lines if l.strip() and l.strip() not in ql)
        exp = re.sub(r"\n(\s*\n)+", "\n", exp).strip()
        exp = re.sub(r"\n\.れ\s*$", "", exp)                   # stray mark at the end of Q1
        exp = exp.replace("(", "（").replace(")", "）")              # half-width brackets would render as furigana
        qs.append({"no": no, "q": qq, "opts": [o.replace("⤴", "") for o in opts], "a": a, "exp": exp})
    return qs


def kaiseki2(print_file, kaiseki_file):
    """組み立て 14-18: question + ★ slot from the class print, order/translation/ポイント from the 解析."""
    pt = "".join(p.get_text() for p in pymupdf.open(N3 / print_file))
    sec = pt.split("問題２", 1)[1].split("問題3", 1)[0]
    kt = page_text(kaiseki_file)
    kb = dict(re.findall(r"(?m)^\s*(1[4-8])\.\s*(.*?)(?=^\s*1[4-8]\.|\Z)", kt, re.S | re.M))
    # ★ slot = which drawn blank the ★ sits on
    doc = pymupdf.open(N3 / print_file)
    slots = []
    for p in doc:
        lines = [d["rect"] for d in p.get_drawings() if d["rect"].height < 2 and d["rect"].width > 20]
        for b in p.get_text("rawdict")["blocks"]:
            for l in b.get("lines", []):
                for sp in l["spans"]:
                    for c in sp["chars"]:
                        if c["c"] == "★":
                            x = (c["bbox"][0] + c["bbox"][2]) / 2
                            row = sorted([r for r in lines if abs(r.y0 - c["bbox"][3]) < 8], key=lambda r: r.x0)
                            if len(row) == 4:
                                slots.append(next(i for i, r in enumerate(row) if r.x0 <= x <= r.x1))
    qs = []
    for m, k in zip(re.finditer(r"(?m)^(1[4-8])\.\s*\n(.*?)(?=^1[4-8]\.|\Z)", sec, re.S), slots):
        no, body = int(m.group(1)), m.group(2)
        body = re.sub(r"\n\s*\d\s*\n", "\n", body)                     # page numbers
        o = re.search(r"\n\s*１．", body)
        q, op = body[:o.start()], body[o.start():]
        opts = [re.sub(r"\s+", "", x) for x in re.split(r"\s*[１-４]．\s*", op.strip())[1:]]
        q = re.sub(r"\s*\n\s*", "", q.strip())
        q = re.sub(r"\s*★\s*", " " + " ".join(["＿＿＿"] * k + ["＿★＿"] + ["＿＿＿"] * (3 - k)) + " ", q)
        q = re.sub(r"\s{4,}", " ", q).strip()
        kb_ = kb[str(no)]
        order = [int(c) for c in re.search(r"解答☞\s*([1-4]{4})", kb_).group(1)]
        exp = "\n".join(l.rstrip() for l in kb_.split("\n")[1:] if l.strip() and not re.fullmatch(r"[\s1-4]+", l))
        exp = exp.split("\n", 1)[1] if exp.startswith(("１．", " １．")) or re.match(r"\s*１．", exp) else exp
        qs.append({"no": no, "q": q, "opts": opts, "a": order[k], "order": order,
                   "exp": exp.strip().replace("(", "（").replace(")", "）")})
    if [q["no"] for q in qs] != list(range(14, 19)):
        sys.exit(f"組み立て: {[q['no'] for q in qs]}")
    return qs


out, PASS = [], []
for f, label in SRCS:
    doc = pymupdf.open(N3 / f)
    qs = mondai1(doc)
    assert [q["no"] for q in qs] == list(range(1, 14)), [q["no"] for q in qs]
    out += [{"src": label, "sec": "問題1", **q} for q in qs]
    q2 = mondai2(doc)
    assert [q["no"] for q in q2] == list(range(14, 19)), [q["no"] for q in q2]
    out += [{"src": label, "sec": "問題2", **q} for q in q2]
    ps, rq = reading(doc)
    pbase = len(PASS)
    PASS.extend(ps)
    out += [{"src": label, **q, "pid": pbase + q["pid"]} for q in rq]
lab = "N3衝刺 11/22（解析）"
k1 = kaiseki1(["聽力/W10-1122/解析Ｎ3　語法問題1　1-5番.pdf", "聽力/W10-1122/解析Ｎ３真題語法問題1　6ー13.pdf"])
assert [q["no"] for q in k1] == list(range(1, 14)), [q["no"] for q in k1]
out += [{"src": lab, "sec": "問題1", **q} for q in k1]
out += [{"src": lab, "sec": "問題2", **q} for q in kaiseki2("聽力/W10-1122/1118修正284期Ｎ3衝刺聴解・文字語彙1122第11回目.pdf",
                                                         "聽力/W10-1122/解析　Ｎ3　問題2　14-18　組み立て　.pdf")]
FWP = str.maketrans({"(": "（", ")": "）"})                            # half-width brackets would render as furigana
PASS = [t.translate(FWP) for t in PASS]
for q in out:
    q["q"] = q["q"].translate(FWP); q["opts"] = [o.translate(FWP) for o in q["opts"]]
(ROOT / "data/handout_pass.json").write_text(json.dumps(PASS, ensure_ascii=False, indent=1), encoding="utf8")
(ROOT / "data/handout_quiz.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf8")
print(len(out), "questions")
