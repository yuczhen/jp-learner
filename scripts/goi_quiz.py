"""語彙 解析 PDFs (teacher's answer sheets) -> practice questions, verbatim.
Each question: sentence (target = the red part), options, answer, teacher's translation/notes.
Answer = the 「解答☞」 digits of its section; the red option must agree (else the question is reported, not guessed).
-> data/goi_quiz.json"""
import json, re, sys
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import furi

B = Path("/Users/yuchicheng/Documents/!!各類課程/2026 東吳日文n3/聽力")
FILES = [  # (file, label)
    ("W4-0913/解析　Ｎ3語彙　問題1-3　　1-25.pdf", "語彙解析 W4（問題1-3 1-25）"),
    ("W6-1004/解析　N3語彙　問題1-2　1-14.pdf", "語彙解析 W6（問題1-2 1-14）"),
    ("W7-1018/解析Ｎ3　語彙　問題3-4.pdf", "語彙解析 W7（問題3-4）"),
    ("W8-1101/解析_Ｎ3語彙_問題5.pdf", "語彙解析 W8（問題5）"),
    ("W9-1108/解析　Ｎ3語彙　問題1-3　1-25.pdf", "語彙解析 W9（問題1-3 1-25）"),
    ("W10-1115/解析　N3語彙　問題4-5　.pdf", "語彙解析 W10（問題4-5）"),
    ("解析Ｎ3_文字語彙問題1-3_１-２５番.pdf", "文字語彙解析（問題1-3 1-25）"),
    ("解析Ｎ3文字語彙_問題4-5_26-35番.pdf", "文字語彙解析（問題4-5 26-35）"),
]
FW = str.maketrans("０１２３４５６７８９", "0123456789")


def red(c):
    return ((c >> 16) & 255) > 0xb0 and ((c >> 8) & 255) < 0x50 and (c & 255) < 0x50


def lines_of(doc):
    """base-size text lines in reading order, red runs marked 《》"""
    out = []
    for p in doc:
        chars = []
        for b in p.get_text("rawdict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    if s["size"] < 8.5:
                        continue
                    for c in s["chars"]:
                        chars.append((c["c"], c["bbox"], s["size"], red(s["color"])))
        chars.sort(key=lambda c: (round((c[1][1] + c[1][3]) / 2 / 6), c[1][0]))
        cur, cy = [], None
        rows = []
        for c in chars:
            y = (c[1][1] + c[1][3]) / 2
            if cy is not None and abs(y - cy) > c[2] * 0.6:
                rows.append(cur); cur = []
            if not cur:
                cy = y
            cur.append(c)
        if cur:
            rows.append(cur)
        for ln in rows:
            o, r = "", False
            for ch, _, _, rd in ln:
                if rd and not r: o += "《"
                if not rd and r: o += "》"
                r = rd; o += ch
            if r: o += "》"
            o = re.sub(r"《\s*》", " ", o).rstrip()
            if o.strip():
                out.append(o)
    return out


KANA_ONLY = re.compile(r"^[ぁ-ゖー《》\s]+$")
QSTART = re.compile(r"^\s*(?:[（(]\s*([0-9０-９]{1,2})\s*[）)]|([0-9０-９]{1,2})\s*[．.\s])\s*(.*)$")
OPT = re.compile(r"(?:^|\s)《?\s*([1-4１-４])\s*[．.\s]\s*《?\s*([^\s《》]+)")
plain = lambda s: s.replace("《", "").replace("》", "")


def parse(file, label):
    doc = pymupdf.open(B / file)
    L = lines_of(doc)
    out, sec, ans, k = [], "", "", 0
    blocks, expect = [], None
    OPT1 = re.compile(r"^\s*《?\s*[1１]\s*[．.\s]")
    for i, l in enumerate(L):
        pl = plain(l)
        m = re.search(r"問題\s*([ⅠⅡⅢ1-5１-５])", pl)
        if m and len(pl.strip()) < 12:
            sec = "問題" + m.group(1).translate(FW).replace("Ⅰ", "1").replace("Ⅱ", "2").replace("Ⅲ", "3")
        a = re.search(r"解答\s*☞\s*([0-9 ]+)", pl.translate(FW))
        if a:
            ans, k = re.sub(r"\s", "", a.group(1)), 0
            if "問題5" in file:
                sec = "問題5"
            continue
        q = QSTART.match(pl.translate(FW))
        n = int(q.group(1) or q.group(2)) if q else None
        rest = q.group(3) if q else ""
        # a question line: numbered as expected, carries the red target inside a longer line
        # (an answer-option line is just a short red word), and option 1 follows within a few lines
        zh_only = lambda x: x.strip() and not re.search(r"[ぁ-ゖァ-ヺ]", x)
        if q and ans and (expect is None or n == expect) and (("《" in l and \
                (len(re.sub(r"[\s*＊]", "", rest)) >= 5 or "*" in rest) and any(OPT1.match(x) for x in L[i + 1:i + 7])) or
                ("《" not in l and "。" in l and i + 2 < len(L) and zh_only(L[i + 1]) and OPT1.match(L[i + 2]))):
            blocks.append({"sec": sec, "no": n, "first": l, "body": [], "ans": ans[k] if k < len(ans) else None})
            k += 1; expect = n + 1
        elif blocks:
            blocks[-1]["body"].append(l)
    return blocks


RUBYLEAK = re.compile(r"^[ぁ-ゖー\s]+$")
MARK = re.compile(r"(?:^|(?<=\s))《?\s*([1-4１-４])\s*[．.\s]\s*")


def options(body, sentence):
    """first 1..4 option of each number after the question; option text = up to its gloss"""
    found = {}
    for l in body:
        pl = plain(l)
        ms = list(MARK.finditer(pl))
        for j, m in enumerate(ms):
            n = int(m.group(1).translate(FW))
            seg = pl[m.end(): ms[j + 1].start() if j + 1 < len(ms) else len(pl)]
            if not re.search(r"[ぁ-ゖァ-ヺ一-龥]", seg) or (sentence and not re.search(r"[ぁ-ゖァ-ヺ]", seg)):
                continue
            if sentence:
                t = re.split(r"\s\*|＊|\s{2,}\(|　{2,}", seg.strip())[0].strip()
            else:
                t = re.split(r"\s{2,}|\s?[(（](?!×)|☞|：|:|\s\*|\s例", seg.strip())[0].strip()
                t = re.sub(r"\s.*$", "", t)
            t = re.sub(r"（×）|\(×\)", "", t).strip()
            red = "《" in l[:l.find(m.group(0).strip()) + 3] if m.group(0).strip() in l else False
            if n not in found and n == len(found) + 1 and t:
                found[n] = (t, l)
    return [found[k][0] for k in sorted(found)], {k: found[k][1] for k in found}


# read off the page by eye where the layout defeats the parser (verbatim from the PDF)
MANUAL = {
    ("語彙解析 W4（問題1-3 1-25）", 10): {"q": "数学の［せいせき］が前よりよくなった。"},          # printed ruby せいせき
    ("語彙解析 W4（問題1-3 1-25）", 11): {"opts": ["爆いて", "燃いて", "煙いて", "焼いて"]},       # "4焼いて" (no dot)
    ("文字語彙解析（問題1-3 1-25）", 10): {"q": "携帯電話を［かり］ました。"},                    # printed ruby か on 借
    # 漢字読み options as printed in furigana over the teacher's kanji
    ("語彙解析 W4（問題1-3 1-25）", 1): {"opts": ["ほそい", "かるい", "まるい", "ひくい"]},
    ("語彙解析 W4（問題1-3 1-25）", 3): {"opts": ["ほうぼう", "ほうごう", "ほうほう", "ほうこう"]},
    ("語彙解析 W9（問題1-3 1-25）", 2): {"opts": ["くばって", "はらって", "かざって", "ひろって"]},   # printed beside the kanji
    ("語彙解析 W4（問題1-3 1-25）", 2): {"opts": ["こうじん", "こじん", "こにん", "こうにん"]},
    ("語彙解析 W4（問題1-3 1-25）", 8): {"opts": ["どりょく", "とりょく", "きょうりょく", "ぎょうりょく"]},
    ("文字語彙解析（問題1-3 1-25）", 1): {"opts": ["かなしい", "くやしい", "くるしい", "さびしい"]},
    ("文字語彙解析（問題1-3 1-25）", 2): {"opts": ["しゅちゅう", "しゅちょう", "しゅっちゅう", "しゅっちょう"]},
    ("文字語彙解析（問題1-3 1-25）", 3): {"opts": ["せき", "かぎ", "あな", "ふた"]},
    ("文字語彙解析（問題1-3 1-25）", 4): {"opts": ["ね", "は", "かわ", "め"]},
    ("文字語彙解析（問題1-3 1-25）", 5): {"opts": ["じこ", "じじょう", "じこう", "じじょ"]},
    ("文字語彙解析（問題1-3 1-25）", 6): {"opts": ["つうち", "えんち", "つうし", "とおし"]},
    ("文字語彙解析（問題1-3 1-25）", 7): {"opts": ["ぜんしゅ", "せんしゅう", "せんしゅ", "ぜんしゅう"]},
    ("文字語彙解析（問題1-3 1-25）", 8): {"opts": ["しつりょく", "じつりょく", "どりょく", "とりょく"]},
    ("語彙解析 W10（問題4-5）", 27): {"q": "その知らせを聞いたとき、私はとても［がっかりした］。", "note": "（失望）"},
    ("語彙解析 W10（問題4-5）", 30): {"q": "ここは［横断禁止］です。"},                           # underlined, not red
    ("語彙解析 W10（問題4-5）", 31): {"opts": ["飛行機の出発時間が遅延になった。", "安いのがなくて、 1 万円もオーバーしてしまった。",
                                       "考えすぎて、頭が痛くなった。", "料理が多すぎて、もう食べられない。"]},
    ("語彙解析 W7（問題3-4）", 24): {"opts": ["止めて（とめて）", "止めて（やめて）", "下げて", "閉じて"]},   # printed ruby と／や
    ("文字語彙解析（問題1-3 1-25）", 22): {"q": "このタオルで、ぬれた手をしっかり（　　）", "note": "濡れる：沾濕"},
}


def reading(text, ctx=None):
    """hiragana of `text` from the furigana printed in the handout (searching ctx first), or None"""
    for c in ([ctx] if ctx else []) + [text]:
        h = furi.handout(c)
        if not h:
            continue
        key, rng, _ = h
        t = re.sub(r"\s", "", text)
        st = key.find(t)
        if st < 0:
            continue
        rd, i, en = "", st, st + len(t)
        for s_, e_, y in sorted(rng):
            if s_ >= st and e_ <= en:
                rd += key[i:s_] + y; i = e_
        rd += key[i:en]
        if not re.search(r"[一-龥々]", rd):
            return rd
    return None


def strip_note(q):
    """teacher's hints after the sentence (e.g. （*逃げる）) give the answer away: move them to the notes"""
    depth, cut = 0, None
    for i, ch in enumerate(q):
        if ch == "［": depth += 1
        elif ch == "］": depth -= 1
        elif ch == "。" and depth == 0:
            cut = i + 1; break
    if cut is None:
        m = re.search(r"\s\*|＊|\*|(?<=］)\s*[（(]|(?<=）)\s*[^\s（）]{0,3}[：:]|\s{2,}", q)
        cut = m.start() if m else len(q)
    return q[:cut].rstrip(), q[cut:].strip()


def build(bl, label):
    out, bad = [], []
    for b in bl:
        sec, no = b["sec"], b["no"]
        first = b["first"]
        m = re.search(r"《([^》]*)》", first)
        tgt = m.group(1).strip() if m else ""
        body = [x for x in b["body"] if not RUBYLEAK.match(plain(x)) and plain(x).strip()]
        if sec == "問題5":
            word = re.sub(r"^\s*[0-9０-９]+\s*[．.]\s*", "", plain(first)).split("*")[0].split("＊")[0].strip()
            word = re.split(r"\s{2,}", word)[0]
            # options: the Japanese sentences (skip the meanings page of 34.詰める)
            opts, raw = options(body, True)
            q = word
        else:
            opts, raw = options(body, False)
            qline = re.sub(r"^\s*(?:[（(]\s*[0-9０-９]{1,2}\s*[）)]|[0-9０-９]{1,2}\s*[．.\s])\s*", "", first)
            if sec == "問題3":
                q = re.sub(r"《\s*[（(]\s*([^）)]*?)\s*[）)]\s*》|[（(]\s*《([^》]*)》\s*[）)]|《([^》]*)》", "（　　）", qline, count=1)
            elif sec == "問題2" and re.search(r"[一-龥]", tgt):
                pq = plain(qline).strip()
                h = furi.handout(pq)
                rd = None
                if h:
                    key, rng, _ = h
                    st = key.find(re.sub(r"\s", "", tgt))
                    if st >= 0:
                        rd, i = "", st
                        en = st + len(re.sub(r"\s", "", tgt))
                        for s_, e_, y in sorted(rng):
                            if s_ >= st and e_ <= en:
                                rd += key[i:s_] + y; i = e_
                        rd += key[i:en]
                        if re.search(r"[一-龥]", rd):
                            rd = None
                if rd is None and (label, no) not in MANUAL:
                    bad.append((label, no, "表記: no printed reading for " + tgt)); continue
                rd = rd or tgt
                q = re.sub(r"《[^》]*》", "［" + rd + "］", qline, count=1)
            else:
                q = re.sub(r"《([^》]*)》", lambda m_: "［" + m_.group(1).strip() + "］", qline, count=1) if tgt else qline
            q = plain(q).strip()
        note = ""
        if sec != "問題5":
            q, note = strip_note(q)
            kanji = [bool(re.search(r"[一-龥々]", o)) for o in opts]
            if sec == "問題1" and len(opts) == 4 and re.search(r"[一-龥々]", tgt) and any(kanji):
                # 漢字読み: the teacher wrote kanji (with furigana) for some options; the question had readings
                new = [reading(o) if k_ else o for o, k_ in zip(opts, kanji)]
                if None not in new:
                    opts = new
                elif (label, no) not in MANUAL:
                    bad.append((label, no, f"reading options not printed: {opts}")); continue
        if (label, no) in MANUAL:
            q = MANUAL[(label, no)].get("q", q); opts = MANUAL[(label, no)].get("opts", opts)
            note = MANUAL[(label, no)].get("note", note)
        a = int(b["ans"]) if b["ans"] else None
        if len(opts) != 4 or not a:
            bad.append((label, no, f"options {opts} ans {a}")); continue
        rl = raw.get(a, "")
        if "《" not in rl:
            bad.append((label, no, f"answer {a} not red: {plain(rl)[:40]}"))
        exp = "\n".join(plain(x).rstrip() for x in body)
        exp = re.sub(r"[ \t\u3000]{3,}", "　", exp)
        if note:
            exp = note + "\n" + exp
        out.append({"src": label, "sec": sec, "no": no, "q": q, "opts": opts, "a": a, "exp": exp})
    return out, bad


if __name__ == "__main__":
    for f, lab in FILES:
        bl = parse(f, lab)
        qs, bad = build(bl, lab)
        ALL = globals().setdefault("ALL", []); ALL += qs
        BAD = globals().setdefault("BAD", []); BAD += bad
        print("=====", lab, len(bl), "->", len(qs))
    for x in BAD: print("CHECK", x)
    FWP = str.maketrans({"(": "（", ")": "）"})
    for q in ALL:
        q["q"] = q["q"].translate(FWP); q["opts"] = [o.translate(FWP) for o in q["opts"]]; q["exp"] = q["exp"].translate(FWP)
    (ROOT / "data/goi_quiz.json").write_text(json.dumps(ALL, ensure_ascii=False, indent=1), encoding="utf8")
    print(len(ALL), "questions")
