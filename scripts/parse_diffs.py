# Parse sigure.tw "A和B的差別" articles (data/raw/diff/*.html) into data/diffs.json.
# Content is kept verbatim from sigure (Japanese with ruby, Chinese translations, explanations);
# only page chrome (menus, buttons, links, ads, images) is removed.
import json, re, html as H
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/diff"
KEEP = {"h2", "h3", "h4", "p", "ol", "ul", "li", "ruby", "rt", "rp", "span", "strong", "b", "br", "div",
        "table", "thead", "tbody", "tr", "th", "td"}
KEEP_CLS = {"keyword", "trans", "keyword-jeans", "block"}


def clean(frag):
    frag = re.sub(r"<nav.*?</nav>|<button.*?</button>|<script.*?</script>|<style.*?</style>|<img[^>]*>|<figure.*?</figure>|<ins.*?</ins>|<iframe.*?</iframe>", "", frag, flags=re.S)
    frag = re.sub(r'<div class="url">.*?</div>', "", frag, flags=re.S)   # "詳細解釋可參考：…" link lines

    def tag(m):
        close, name, attrs = m.group(1), m.group(2).lower(), m.group(3) or ""
        if name not in KEEP:
            return ""
        if close:
            return f"</{name}>"
        if name in ("span", "div"):
            c = re.search(r'class="([^"]*)"', attrs)
            c = [x for x in (c.group(1).split() if c else []) if x in KEEP_CLS]
            if 'lang="ja"' in attrs:
                c.append("ja")
            return f'<{name} class="{" ".join(c)}">' if c else f"<{name}>"
        return f"<{name}>"
    frag = re.sub(r"<(/?)([a-zA-Z0-9]+)([^>]*)>", tag, frag)
    vip = re.search(r"<h3>\s*VIP", frag)
    if vip:                                           # members-only rest of the article: keep the public part
        frag = frag[:vip.start()]
    for _ in range(4):
        frag = re.sub(r"<div>\s*</div>|<p>\s*</p>|<span>\s*</span>|<p>(&nbsp;|\s)*</p>", "", frag)
        frag = re.sub(r"(\s*<div>)+\s*$", "", frag)   # unclosed wrappers left where the public part ends
    return re.sub(r"\n\s*\n+", "\n", frag).strip()


def text(fr):
    fr = re.sub(r"<rt>.*?</rt>|<rp>.*?</rp>", "", fr, flags=re.S)
    return H.unescape(re.sub(r"<[^>]+>", "", fr)).strip()


def terms_of(title):
    t = re.sub(r"的差別.*$|的差異.*$|的區別.*$", "", title)
    q = re.findall(r"「([^」]+)」", t)
    return q


out = {}
for f in sorted(RAW.glob("*.html")):
    if f.name.startswith("_"):
        continue
    h = f.read_text(encoding="utf8")
    m = re.search(r'<h1 class="article__title">(.*?)</h1>', h, re.S)
    c = re.search(r'<section class="article__content prose">(.*?)</section>', h, re.S)
    if not m or not c:
        continue
    title = text(m.group(1))
    body = clean(c.group(1))
    # example sentences with marked keyword, grouped by the nearest preceding heading
    exs, head = [], ""
    for tok in re.finditer(r"<h[234]>(.*?)</h[234]>|<li>(.*?)</li>", body, re.S):
        if tok.group(1) is not None:
            head = text(tok.group(1)); continue
        li = tok.group(2)
        ja = re.search(r'<span class="ja">(.*)</span>\s*(?:<br>)', li, re.S) or re.search(r'<span class="ja">(.*?)</span>\s*$', li, re.S)
        if not ja or 'class="keyword"' not in li:
            continue
        kws = re.findall(r'<span class="keyword">(.*?)</span>', ja.group(1), re.S)
        tr = re.search(r'<span class="trans">(.*?)</span>\s*$', li, re.S) or re.search(r'<span class="trans">(.*)', li, re.S)
        exs.append({"h": head, "ja": ja.group(1), "kw": [text(k) for k in kws],
                    "zh": text(re.sub(r'<span class="keyword-jeans">.*?</span>', "", tr.group(1))) if tr else ""})
    out[f.stem] = {"slug": f.stem, "title": title, "terms": terms_of(title), "html": body, "ex": exs,
                   "vip": "VIP 專屬內容" in c.group(1),
                   "url": f"https://www.sigure.tw/learn-japanese/mix/difference/{f.stem}"}

(ROOT / "data/diffs.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf8")
print(len(out), "articles;", sum(len(v["ex"]) for v in out.values()), "keyword examples")


# ---- 易混練習: blank the sigure-marked keyword; options = the article's compared terms.
# Only examples whose answer is unambiguous from the article itself:
#   (a) the example sits under a heading naming exactly one term and its keyword is that term, or
#   (b) the article marks the other term(s) as wrong for that sentence (✖ / ❌ notes).
def split_terms(ts):
    r = []
    for t in ts:
        r += [x.strip() for x in re.split(r"[、・，,／/]", t) if x.strip()]
    return r


def kw_match(t, k):
    return k == t or k.startswith(t) or (len(t) >= 2 and k.startswith(t[:-1]))


BOTH = ("皆可", "都可", "都能", "兩者", "共通", "相同", "通用", "差別", "差異", "區別", "總結", "比較")
quiz = []
for slug, v in out.items():
    v["terms"] = split_terms(v["terms"])
    ts = v["terms"]
    if not (2 <= len(ts) <= 4):
        continue
    for m in re.finditer(r"<h[234]>(.*?)</h[234]>|<li>(.*?)</li>", v["html"], re.S):
        if m.group(1) is not None:
            head = text(m.group(1)); continue
        li = m.group(2)
        ja = re.search(r'<span class="ja">(.*)</span>\s*<br>', li, re.S)
        if not ja or ja.group(1).count('class="keyword"') != 1 or "❌" in li[:ja.start() + 5]:
            continue
        k = text(re.search(r'<span class="keyword">(.*?)</span>', ja.group(1), re.S).group(1))
        hit = [t for t in ts if kw_match(t, k)]
        if len(hit) != 1:
            continue
        ans = hit[0]
        wrong_marked = re.findall(r"[✖×❌]\s*([^）)\s]+)", text(li))
        in_head = [t for t in ts if t in head]
        ok = (in_head == [ans] and not any(b in head for b in BOTH)) or \
             (wrong_marked and all(any(kw_match(o, w) or w.startswith(o) for w in wrong_marked) for o in ts if o != ans))
        if not ok or re.search(r"[✖×❌]", text(ja.group(1))):
            continue
        q = re.sub(r'<span class="keyword">.*?</span>', '<span class="blank">（　　）</span>', ja.group(1), count=1, flags=re.S)
        tr = re.search(r'<span class="trans">(.*?)</span>\s*$', li, re.S) or re.search(r'<span class="trans">(.*)', li, re.S)
        zh = text(re.sub(r'<span class="keyword-jeans">.*?</span>', "", tr.group(1))) if tr else ""
        quiz.append({"slug": slug, "q": q, "full": ja.group(1), "opts": ts, "a": ans, "zh": zh})

(ROOT / "data/diffs.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf8")
(ROOT / "data/diff_quiz.json").write_text(json.dumps(quiz, ensure_ascii=False), encoding="utf8")
print(len(quiz), "quiz items from", len({q["slug"] for q in quiz}), "articles")
