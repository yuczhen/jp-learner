"""Text -> what the TTS should read (kana based, so kanji are never guessed)."""
import re

KANJI = re.compile(r"[一-鿿々]")
RUBY = re.compile(r"([一-鿿々ァ-ヶー]+)\(([^)]+)\)")


ALT = re.compile(r"[｛{]([^｝}]*)[｝}]")


def first_alt(t):
    """｛きり／だけ／のみ｝ -> きり  (read one option, never all of them); drop stray trailing slashes"""
    t = ALT.sub(lambda m: re.split(r"[／/]", m.group(1))[0], t)
    return re.sub(r"[／/]\s*$", "", t)


_TOK = None


def _tokenizer():
    """Sudachi is only installed locally; in CI (no sudachipy) particles are left untouched."""
    global _TOK
    if _TOK is None:
        try:
            from sudachipy import dictionary, tokenizer
            _TOK = (dictionary.Dictionary().create(), tokenizer.Tokenizer.SplitMode.C)
        except Exception:
            _TOK = False
    return _TOK


RUBY_SEG = re.compile(r"([\u4e00-\u9fff々ァ-ヶー]+)\s*\(([^)]+)\)")


def fix_particles(ruby):
    """kana text where the particles は/へ are written as わ/え (so TTS says 'wa'/'e').
    Particle detection runs on the original kanji sentence (needs the kanji context)."""
    tk = _tokenizer()
    if not tk:
        return RUBY_SEG.sub(lambda m: m.group(2) if KANJI.search(m.group(1)) else m.group(1), ruby)
    plain, kana, kmap = [], [], {}
    last = 0
    for m in RUBY_SEG.finditer(ruby):
        for ch in ruby[last:m.start()]:                    # plain kana/punctuation between ruby segments
            kmap[len(plain)] = len(kana)
            plain.append(ch); kana.append(ch)
        base, rd = m.group(1), m.group(2)
        plain.extend(base)
        kana.extend(rd if KANJI.search(base) else base)
        last = m.end()
    for ch in ruby[last:]:
        kmap[len(plain)] = len(kana)
        plain.append(ch); kana.append(ch)
    text = "".join(plain)
    dic, mode = tk
    pos = 0
    for m in dic.tokenize(text, mode):
        surf = m.surface()
        end = pos + len(surf) - 1
        if m.part_of_speech()[0] == "助詞" and surf[-1:] in ("は", "へ") and end in kmap:
            kana[kmap[end]] = "わ" if surf[-1] == "は" else "え"
        pos += len(surf)
    return "".join(kana)


def sentence_text(ruby):
    """example sentence -> text read aloud (kana for kanji, katakana kept, particles fixed)."""
    ruby = first_alt(ruby).replace("()", "")
    return fix_particles(ruby)


def word_text(word, reading):
    """vocab entry -> text read aloud. Hints in （…） are READ (so the audio matches what is written);
    （＝…） alternatives are spoken after a pause; digits/notes in parentheses are dropped."""
    alts = re.findall(r"（＝([^）]*)）", reading)
    r = re.sub(r"（＝[^）]*）", "", reading)
    base = word if not KANJI.search(word) and re.search(r"[ァ-ヶ]", word) else r

    def paren(m):
        inner = m.group(1)
        if re.search(r"\d", inner):
            return ""
        return re.split(r"[／/]", inner)[0]          # （友だちに／先生に） -> 友だちに
    base = re.sub(r"[（(]([^）)]*)[）)]", paren, base)
    base = re.sub(r"[～〜＝：:①②③]", "", base).strip()
    alts = [re.sub(r"[（(]([^）)]*)[）)]", paren, a) for a in alts]
    alts = [re.sub(r"[～〜＝]", "", a).strip() for a in alts]
    return "。 ".join([x for x in [base] + alts if x])
