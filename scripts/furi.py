"""Furigana helpers: '漢字(よみ)' strings <-> plain text + reading ranges; handout lookup; merge.
Printed (source) readings always win; tool readings only fill kanji the source left without furigana."""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KANJI = re.compile(r"[一-鿿々〆ヶ]")
WS = re.compile(r"[\s　]")


def parse(r):
    """'私(わたし)は学生(がくせい)' -> ('私は学生', [(0,1,'わたし'), (2,4,'がくせい')]); reading applies to the
    kanji run right before '('."""
    plain, rng = "", []
    for m in re.finditer(r"([^()]*?)\(([^()]*)\)|([^()]+)$", r):
        if m.group(3) is not None:
            plain += m.group(3); continue
        base, y = m.group(1), m.group(2)
        k = len(base)
        while k > 0 and KANJI.match(base[k - 1]):
            k -= 1
        if k == len(base) or not re.fullmatch(r"[ぁ-ゖー・]+", y):      # katakana gloss etc.: keep as text
            plain += base + f"({y})" if k == len(base) else base
            if k != len(base):
                rng.append((len(plain) - (len(base) - k), len(plain), y))
            continue
        plain += base
        rng.append((len(plain) - (len(base) - k), len(plain), y))
    return plain, rng


def build(plain, rng):
    out, i = "", 0
    for s, e, y in sorted(rng):
        out += plain[i:s] + plain[s:e] + f"({y})"; i = e
    return out + plain[i:]


_H = None
def handout(ja):
    """Readings printed in the handout PDFs for this sentence: (plain, ranges, file) or None."""
    global _H
    if _H is None:
        p = ROOT / "data/handout_ruby.json"
        _H = json.loads(p.read_text(encoding="utf8"))["pages"] if p.exists() else []
    key = WS.sub("", ja)
    if not key:
        return None
    for pg in _H:
        t = pg["t"]
        pos = [i for i, ch in enumerate(t) if not WS.match(ch)]
        flat = "".join(t[i] for i in pos)
        k = flat.find(key)
        if k < 0:
            continue
        a, b = pos[k], pos[k + len(key) - 1] + 1
        rng = [(r[0], r[1], r[2]) for r in pg["r"] if a <= r[0] and r[1] <= b]
        # map page offsets -> offsets in `key`
        idx = {p_: j for j, p_ in enumerate(pos[k:k + len(key)])}
        return key, [(idx[s], idx[e - 1] + 1, y) for s, e, y in rng], pg["f"]
    return None


def merge(src_plain, src_rng, tool_ruby):
    """Source ranges + tool ranges for kanji not covered by the source. Returns (ruby, tool_ranges_used)."""
    tp, trng = parse(tool_ruby)
    if WS.sub("", tp) != src_plain:
        return None, []
    # tool offsets on whitespace-free text
    pos = [i for i, ch in enumerate(tp) if not WS.match(ch)]
    inv = {p_: j for j, p_ in enumerate(pos)}
    covered = set()
    for s, e, _ in src_rng:
        covered.update(range(s, e))
    used = []
    for s, e, y in trng:
        if s not in inv or (e - 1) not in inv:
            continue
        s2, e2 = inv[s], inv[e - 1] + 1
        if not covered.intersection(range(s2, e2)):
            used.append((s2, e2, y))
    return build(src_plain, list(src_rng) + used), used
