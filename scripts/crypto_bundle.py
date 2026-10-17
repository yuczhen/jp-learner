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
    ls_path = Path(src_dir) / "listening.json"
    if ls_path.exists():
        data["listening"] = json.loads(ls_path.read_text(encoding="utf8"))
    ai_path = Path(src_dir) / "audio_index.json"          # clip id -> pack name
    if ai_path.exists():
        data["audio_index"] = json.loads(ai_path.read_text(encoding="utf8"))
    ex_path = Path(src_dir) / "examples_final.json"
    if ex_path.exists():                                   # one example sentence per vocab word
        ex = json.loads(ex_path.read_text(encoding="utf8"))
        for e in data["vocab"]:
            if e["id"] in ex:
                e["ex"] = {"ja": _clean(ex[e["id"]]["ja"]), "ruby": _clean(ex[e["id"]]["ruby"]), "zh": ex[e["id"]]["zh"]}
    for g in data["grammar"].values():
        for x in g["examples"]:
            x["ruby"] = _kata(x["ruby"])
            x["ja"] = _clean(x["ja"])
        for c in g.get("class", []):
            for x in c["examples"]:
                x["ruby"] = _kata(x["ruby"])
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
