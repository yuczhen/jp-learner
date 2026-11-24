"""AES-256-GCM bundle of the private data files (password via env DATA_PASSWORD).
Format: b"JPL1" | salt(16) | iv(12) | ciphertext+tag. Key = PBKDF2-HMAC-SHA256, 600k iters."""
import json, os, sys
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT = Path(__file__).resolve().parent.parent
NAMES = ("plan", "grammar", "vocab")
OUT = ROOT / "docs" / "data" / "bundle.enc"
ITER = 600_000


def get_salt():
    """reuse the salt of the published bundle so audio packs stay valid when the bundle is re-encrypted"""
    if OUT.exists() and OUT.read_bytes()[:4] == b"JPL1":
        return OUT.read_bytes()[4:20]
    return os.urandom(16)


def encrypt_blob(raw, pw):
    salt, iv = get_salt(), os.urandom(12)
    return b"JPA1" + iv + AESGCM(_key(pw, salt)).encrypt(iv, raw, None)


def decrypt_blob(path, pw):
    b = Path(path).read_bytes()
    assert b[:4] == b"JPA1"
    salt = get_salt()
    return AESGCM(_key(pw, salt)).decrypt(b[4:16], b[16:], None)


def _key(pw, salt):
    return PBKDF2HMAC(hashes.SHA256(), 32, salt, ITER).derive(pw.encode())


import re
def _clean(s):
    s = s.replace("()", "").replace("（）", "")
    s = re.sub(r"([\u4e00-\u9fff々ァ-ヶー])\s+\(", r"\1(", s)          # "暑 (あつ)" -> "暑(あつ)"
    return re.sub(r"[／/]\s*$", "", s)


def _kata(s):
    """add hiragana reading after katakana runs that have none yet"""
    h = lambda t: "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in t)
    return re.sub(r"([ァ-ヴー]+)(?![\(ァ-ヴー])", lambda m: f"{m.group(1)}({h(m.group(1))})" if re.search(r"[ァ-ヴ]", m.group(1)) else m.group(1), _clean(s))


def encrypt(src_dir, pw):
    data = {n: json.loads((Path(src_dir) / f"{n}.json").read_text(encoding="utf8")) for n in NAMES}
    merged = Path(src_dir) / "grammar_merged.json"      # grammar + class-handout sections (local only)
    if merged.exists():
        data["grammar"] = json.loads(merged.read_text(encoding="utf8"))
    cmp_path = Path(src_dir) / "compare.json"           # similar-grammar comparison tables
    if cmp_path.exists():
        data["compare"] = json.loads(cmp_path.read_text(encoding="utf8"))
    vx_path = Path(src_dir) / "vocab_extra.json"          # hand-picked extra words (curated batches)
    if vx_path.exists():
        have = {e["id"] for e in data["vocab"]}
        data["vocab"] += [e for e in json.loads(vx_path.read_text(encoding="utf8")) if e["id"] not in have]
    tp_path = Path(src_dir) / "topics.json"               # topic index page (all word groups)
    if tp_path.exists():
        data["topics"] = json.loads(tp_path.read_text(encoding="utf8"))
    ls_path = Path(src_dir) / "listening.json"
    if ls_path.exists():
        data["listening"] = json.loads(ls_path.read_text(encoding="utf8"))
        lc_path = Path(src_dir) / "listen_choices.json"       # answer options for the listening questions
        if lc_path.exists():
            lc = json.loads(lc_path.read_text(encoding="utf8"))
            for it in data["listening"]:
                if it["id"] in lc:
                    it.update({k: v for k, v in lc[it["id"]].items() if k in ("qs", "c", "a", "n", "pic", "bk", "trk")})
    lx_path = Path(src_dir) / "listening_extra.json"      # class-print listening (script/options from the handout)
    if lx_path.exists():
        for x in json.loads(lx_path.read_text(encoding="utf8")):
            x.pop("audio", None); x["x"] = 1
            data.setdefault("listening", []).append(x)
    df_path = Path(src_dir) / "diffs.json"                 # sigure "A和B的差別" articles (verbatim)
    dm_path = Path(src_dir) / "diff_match.json"
    if df_path.exists() and dm_path.exists():
        dfs = json.loads(df_path.read_text(encoding="utf8"))
        data["dmatch"] = json.loads(dm_path.read_text(encoding="utf8"))
        used = {s for v in data["dmatch"].values() for s in v}
        data["diffs"] = {s: {k: dfs[s][k] for k in ("title", "terms", "html", "url", "vip")} for s in used}
    # practice quizzes built by script (dquiz/gquiz) removed 2026-11-22: owner wants only questions printed in the handouts
    hp_path = Path(src_dir) / "handout_pass.json"         # reading passages (verbatim) for the handout questions
    if hp_path.exists():
        data["hpass"] = json.loads(hp_path.read_text(encoding="utf8"))
    hq_path = Path(src_dir) / "handout_quiz.json"         # questions printed in the handouts (answer = red box)
    if hq_path.exists():
        from build_examples import tok, MODE, ruby as _rb
        R = lambda t: _kata(_rb(tok.tokenize(t, MODE))) if t.strip() else t
        hq = json.loads(hq_path.read_text(encoding="utf8"))
        hx_path = Path(src_dir) / "handout_quiz_extra.json"   # tests shown in the class videos (answers on screen)
        if hx_path.exists():
            cur = None
            for q in json.loads(hx_path.read_text(encoding="utf8")):
                if q.get("passage"):                          # passage shown above its questions
                    data.setdefault("hpass", []).append(q.pop("passage")); cur = len(data["hpass"]) - 1
                    q["pid"] = cur
                elif q.pop("same_passage", False):
                    q["pid"] = cur
                hq.append(q)
        gq_path = Path(src_dir) / "goi_quiz.json"           # 語彙 解析 PDFs (answers = 解答☞, teacher's notes)
        if gq_path.exists():
            hq += json.loads(gq_path.read_text(encoding="utf8"))
        data["hquiz"] = [{**q, "qr": "\n".join(R(l) for l in q["q"].split("\n")), "or": [R(o) for o in q["opts"]]} for q in hq]
    jl_path = Path(src_dir) / "jlpt.json"
    if jl_path.exists():
        data["jlpt"] = json.loads(jl_path.read_text(encoding="utf8"))
    ai_path = Path(src_dir) / "audio_index.json"          # clip id -> pack name
    if ai_path.exists():
        data["audio_index"] = json.loads(ai_path.read_text(encoding="utf8"))
    ex_path = Path(src_dir) / "examples_final.json"
    if ex_path.exists():                                   # one example sentence per vocab word
        ex = json.loads(ex_path.read_text(encoding="utf8"))
        for e in data["vocab"]:
            if e.get("ex"):
                e["ex"] = {"ja": _clean(e["ex"]["ja"]), "ruby": _clean(e["ex"]["ruby"]), "zh": e["ex"]["zh"], "src": e["ex"].get("src", "")}
            elif e["id"] in ex:
                e["ex"] = {"ja": _clean(ex[e["id"]]["ja"]), "ruby": _clean(ex[e["id"]]["ruby"]), "zh": ex[e["id"]]["zh"], "src": ex[e["id"]].get("src", "")}
    # furigana: printed by the source first (sigure pages, handout PDFs); the tool (Sudachi) only fills kanji the
    # source left without furigana, and every tool reading is listed in data/furi_review.json for checking.
    # Checked corrections (Claude, owner approved 2026-11-22) come from data/furi_fix.json {plain sentence: ruby}.
    import furi
    # drop "examples" that are really sigure's Chinese explanation text (scraping mistake), not Japanese sentences
    _ZH = re.compile(r"[的是為麼們這說會與從還裡個過對於時當並則]")
    def _is_zh(t):
        t2 = re.sub(r"「[^」]*」", "", t)
        return len(_ZH.findall(t2)) >= 2 and len(re.findall(r"[ぁ-ゖァ-ヺ]", t2)) <= len(_ZH.findall(t2)) * 2
    for e in data["vocab"]:
        if e.get("ex") and _is_zh(e["ex"]["ja"]):
            e.pop("ex")
    for g in data["grammar"].values():
        g["examples"] = [x for x in g["examples"] if not _is_zh(x["ja"])]
    sr_path = Path(src_dir) / "sigure_ruby.json"
    SR = {re.sub(r"[\s　]", "", k): v for k, v in json.loads(sr_path.read_text(encoding="utf8")).items()} if sr_path.exists() else {}
    ff_path = Path(src_dir) / "furi_fix.json"      # [context in sentence, kanji, tool reading, checked reading]
    FIX = json.loads(ff_path.read_text(encoding="utf8")) if ff_path.exists() else []
    def _fix(ja, r):
        for fx in FIX:
            c, old, new = (fx[0], f"{fx[1]}({fx[2]})", f"{fx[1]}({fx[3]})") if len(fx) == 4 else fx
            if c in ja and old in r:
                r = r.replace(old, new); stats["checked"] += 1
        return r
    review, stats = [], {"sigure": 0, "handout": 0, "checked": 0, "tool": 0}
    from build_examples import tok as _tok, MODE as _MODE, ruby as _rb2
    def _furi(ja, tool, where):
        key = re.sub(r"[\s　]", "", ja)
        def _chunk(c):   # Chinese notes inside examples (no hiragana outside 「」) get no Japanese readings
            if not c.strip() or re.search(r"[說們這麼嗎呢樣裡讓應擇做會對當從與]", c) or \
                    (not re.search(r"[ぁ-ゖ]", re.sub(r"「[^」]*」", "", c)) and len(re.findall(r"[\u4e00-\u9fff]", c)) >= 2):
                return c
            return _rb2(_tok.tokenize(c, _MODE))
        tool = "\n".join("".join(_chunk(c) for c in re.split(r"(\s+|(?<=[。？！?]))", l)) for l in ja.split("\n"))
        if key in SR:
            stats["sigure"] += 1; return SR[key]
        h = furi.handout(ja)
        if h:
            r, used = furi.merge(h[0], h[1], tool)
            if r is not None:
                stats["handout"] += 1
                if used:
                    review.append({"t": h[0], "w": [[h[0][a:b], y] for a, b, y in used], "at": where})
                return _fix(ja, r)
        pl, rng = furi.parse(tool)
        if rng:
            stats["tool"] += 1
            review.append({"t": pl, "w": [[pl[a:b], y] for a, b, y in rng], "at": where})
        return _fix(ja, tool)
    for e in data["vocab"]:
        if e.get("ex"):
            e["ex"]["ruby"] = _kata(_furi(e["ex"]["ja"], e["ex"]["ruby"], "vocab"))
    for g in data["grammar"].values():
        for x in g["examples"]:
            x["ruby"] = _kata(_furi(x["ja"], x["ruby"], "grammar"))
            x["ja"] = _clean(x["ja"])
        for c in g.get("class", []):
            for x in c["examples"]:
                x["ruby"] = _kata(_furi(x.get("ja") or furi.parse(x["ruby"])[0], x["ruby"], "class"))
    for it in data.get("listening", []):
        for ln in it.get("lines", []):
            ln["ruby"] = _kata(_furi(ln["ja"], ln["ruby"], "listening"))
    for q in data.get("hquiz", []):
        q["qr"] = "\n".join(_kata(_furi(l, r, "practice")) for l, r in zip(q["q"].split("\n"), q["qr"].split("\n")))
        q["or"] = [_kata(_furi(o, r, "practice")) for o, r in zip(q["opts"], q["or"])]
        if q.get("q") and "\n" in q["q"] and "qr" not in q:
            pass
        if q.get("ans"):
            q["ar"] = _kata(_furi(q["ans"], q["ans"], "practice"))
        if "語彙解析" in q["src"]:              # no furigana where it would give the answer away
            if q["sec"] == "問題1":
                q["qr"] = re.sub(r"［[^］]*］", lambda m: re.sub(r"\([^()]*\)", "", m.group(0)), q["qr"])
            if q["sec"] == "問題2":
                q["or"] = list(q["opts"])
        if q.get("exp") and "語彙解析" in q["src"]:     # teacher's notes mix Chinese and fake distractors: printed furigana only
            def _src_only(l):
                k_ = re.sub(r"[\s　]", "", l)
                if k_ in SR:
                    return SR[k_]
                h = furi.handout(l)
                if not h:
                    return l
                pos = [i for i, ch in enumerate(l) if not re.match(r"[\s　]", ch)]   # back to the spaced line
                return furi.build(l, [(pos[a_], pos[b_ - 1] + 1, y) for a_, b_, y in h[1]])
            q["er"] = "\n".join(_kata(_src_only(l)) if l.strip() else l for l in q["exp"].split("\n"))
        elif q.get("exp"):
            q["er"] = "\n".join(_kata(_furi(l, l, "practice")) for l in q["exp"].split("\n"))
    data["hpass"] = ["\n".join(_kata(_furi(l, l, "practice")) for l in t.split("\n")) for t in data.get("hpass", [])]
    # JLPT sample questions that also appear in the teacher's handouts: attach the teacher's 解析 (same answer only)
    _N = lambda t: re.sub(r"[^ぁ-ゖァ-ヺ一-龥々ー]", "", re.sub(r"\([ぁ-ゖー]+\)", "", t or ""))
    _hk = [(_N(q["q"]), q) for q in data.get("hquiz", []) if q.get("er")]
    _oc = lambda cs: tuple(sorted(_N(c) for c in cs))
    for st in (data.get("jlpt") or {}).get("sets", []):
        for sec in st["sections"]:
            for it in sec["items"]:
                k, oc = _N(it.get("q", "")), _oc(it.get("c", []))
                m = [q for kk, q in _hk if q["a"] == it["a"] and (
                     (len(k) >= 8 and len(kk) >= 8 and (k[:10] == kk[:10] or (len(k) >= 14 and len(kk) >= 14 and (k[2:14] in kk or kk[2:14] in k))))
                     or (len(oc) >= 3 and oc == _oc(q["opts"]) and sum(map(len, oc)) >= 8))]
                if m:
                    it["tx"], it["txs"] = m[0]["er"], f"{m[0]['src']} 第{m[0]['no']}題"
    (Path(src_dir) / "furi_review.json").write_text(json.dumps(review, ensure_ascii=False, indent=0), encoding="utf8")
    print("furigana:", stats)
    # PRINCIPLES.md: drop text that was written / translated by the assistant
    lt_path = Path(src_dir) / "listen_titles.json"         # source audio file (Track no.), shown under the title
    lt = json.loads(lt_path.read_text(encoding="utf8")) if lt_path.exists() else {}
    for it in data.get("listening", []):
        it["src"] = it.get("src") or lt.get(it["id"], "")
    for it in data.get("listening", []):
        # line translations: by Claude (owner approved 2026-11-21, the handouts have none), reviewed line by line
        it["notes"] = []; it["ans"] = ""
        for q_ in it.get("qs", []) or []:
            if not it.get("x"): q_["e"] = ""
    for st in (data.get("jlpt") or {}).get("sets", []):
        for sec in st["sections"]:
            for it in sec["items"]:
                it["e"] = ""; it.pop("script", None)
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    salt, iv = get_salt(), os.urandom(12)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(b"JPL1" + salt + iv + AESGCM(_key(pw, salt)).encrypt(iv, raw, None))


def decrypt(path, pw, full=False):
    b = Path(path).read_bytes()
    assert b[:4] == b"JPL1"
    salt, iv, ct = b[4:20], b[20:32], b[32:]
    d = json.loads(AESGCM(_key(pw, salt)).decrypt(iv, ct, None))
    return d if full else (d["plan"], d["grammar"], d["vocab"])


if __name__ == "__main__":
    pw = os.environ.get("DATA_PASSWORD")
    if not pw:
        sys.exit("set DATA_PASSWORD (see .env)")
    encrypt(ROOT / "data", pw)
    print("wrote", OUT, OUT.stat().st_size, "bytes")
