"""Furigana exactly as printed by sigure: every <span lang="ja"> sentence in the downloaded sigure pages
-> data/sigure_ruby.json {plain sentence: "漢字(よみ)..."}  (no tool-made readings)."""
import glob, html as H, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
out = {}
for f in glob.glob(str(ROOT / "data/raw/*.html")) + glob.glob(str(ROOT / "data/raw/diff/*.html")):
    s = open(f, encoding="utf8").read()
    for m in re.finditer(r'<span lang="ja">((?:(?!<span lang="ja">|</li>).)*?)</span>\s*(?=<button|<br|</li|</p|</td|$)', s, re.S):
        frag = re.sub(r"<rp>.*?</rp>", "", m.group(1), flags=re.S)
        rb = re.sub(r"<ruby>(.*?)<rt>(.*?)</rt></ruby>", lambda r: f"{re.sub('<[^>]+>', '', r.group(1))}({r.group(2)})", frag, flags=re.S)
        rb = H.unescape(re.sub(r"<[^>]+>", "", rb)).strip()
        plain = re.sub(r"\(([^()]*)\)", "", rb)
        if "<ruby>" in m.group(1) and plain:
            out.setdefault(plain, rb)
(ROOT / "data/sigure_ruby.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf8")
print(len(out), "sigure sentences with original furigana")
