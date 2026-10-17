"""Send the daily Telegram digest (compact) + one mp3 of the key words/examples.

env: TG_TOKEN, TG_CHAT_ID, SITE_URL, DATA_PASSWORD (all private; see .env, never committed)
usage: notify.py --slot am|pm [--date YYYY-MM-DD] [--dry-run] [--no-audio]
"""
import argparse, asyncio, html, json, os, re, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
KEY_WORDS = 10          # words listed in Telegram (full list is on the web page)
FEMALE, MALE = "ja-JP-NanamiNeural", "ja-JP-KeitaNeural"   # odd days female, even days male (one voice per day)


def load():
    enc = DATA / "bundle.enc"
    pw = os.environ.get("DATA_PASSWORD")
    if enc.exists() and pw:
        sys.path.insert(0, str(ROOT / "scripts"))
        from crypto_bundle import decrypt
        return decrypt(enc, pw)
    return [json.loads((ROOT / "data" / f"{n}.json").read_text(encoding="utf8")) for n in ("plan", "grammar", "vocab")]


def short_title(t):
    return re.sub(r"^N\d文法\d+", "", t).strip()


def load_full():
    enc = DATA / "bundle.enc"
    pw = os.environ.get("DATA_PASSWORD")
    if enc.exists() and pw:
        sys.path.insert(0, str(ROOT / "scripts"))
        from crypto_bundle import decrypt
        return decrypt(enc, pw, full=True)
    out = {}
    for k, f in (("compare", "compare.json"), ("listening", "listening.json")):
        p = ROOT / "data" / f
        out[k] = json.loads(p.read_text(encoding="utf8")) if p.exists() else []
    return out


def compose(plan, G, V, day, batch, site, compare=()):
    """Telegram = a compact digest only. Details (connection, examples, translations, audio) live on the web page."""
    vi = {e["id"]: e for e in V}
    h = html.escape
    am = batch["slot"] == "am"
    dot, sun = ("🟠", "☀️") if am else ("🔵", "🌙")      # colour cue: orange = morning, blue = evening
    label = "早" if am else "晚"
    kind = "複習" if batch["kind"] == "review" else "新"
    out = [f"{dot*4} {sun} <b>{label}</b> {sun} {dot*4}",
           f"<b>Day {day['day']}/{plan['total_days']}</b>（{kind}）· {h(batch['theme'])}"]
    out.append(f"\n{dot} <b>文法</b>（{len(batch['grammar'])}）")
    for i, gid in enumerate(batch["grammar"], 1):
        g = G[gid]
        tag = "".join(f" 📚{h(c['lesson'])}" for c in g.get("class", []))[:14]
        out.append(f"{i}. {h(short_title(g['title'])[:44])}{tag}")
    ids = batch["vocab"]
    out.append(f"\n{dot} <b>單字</b>（精選 {min(KEY_WORDS, len(ids))}／共 {len(ids)}）")
    for wid in ids[:KEY_WORDS]:
        e = vi[wid]
        out.append(f"• {h(e['word'])}　{h(e['reading'])}　{h(e['romaji'])}　{h(e['gloss'][:20])}")
    fam = [f["title"] for f in compare if set(f["members"]) & set(batch["grammar"])][:2]
    if fam:
        out.append("\n📊 對照表：" + "、".join(h(t[:18]) for t in fam))
    if batch.get("review"):
        out.append("🔁 複習：" + "、".join(h(short_title(G[i]["title"])[:14]) for i in batch["review"][:3]))
    if site:
        out.append(f"\n🔗 例句・發音・對照表：{site}#d{day['day']}-{batch['slot']}")
    return "\n".join(out)[:4000]


def audio_script(G, V, batch):
    """short mp3 for Telegram: just the key words, read slowly (kana based)"""
    sys.path.insert(0, str(ROOT / "scripts"))
    from tts_text import word_text
    vi = {e["id"]: e for e in V}
    return "。\n".join(t for t in (word_text(vi[w]["word"], vi[w]["reading"]) for w in batch["vocab"][:KEY_WORDS]) if t)


async def make_mp3(text, path, day=1):
    import edge_tts
    await edge_tts.Communicate(text, FEMALE if day % 2 == 1 else MALE, rate="-10%").save(path)


def tg(token, method, **kw):
    import requests
    files = kw.pop("files", None)
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", data=kw, files=files, timeout=60)
    if not r.ok:
        raise RuntimeError(f"{method} failed: {r.status_code} {r.text[:200]}")


def _diagnose(token, chat):
    """Non-secret hints for debugging bad secrets (never prints the token or the full chat id)."""
    import requests
    try:
        me = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=30).json()
        who = "@" + me["result"]["username"] if me.get("ok") else f"getMe failed: {me.get('error_code')}"
    except Exception as e:
        who = f"getMe error: {type(e).__name__}"
    kind = "numeric" if re.fullmatch(r"-?\d+", chat) else "NOT numeric (should be digits only)"
    print(f"[diag] token belongs to: {who} | chat id: {len(chat)} chars, {kind}, starts with {chat[:2]}...", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", required=True, choices=["am", "pm"])
    ap.add_argument("--date")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-audio", action="store_true")
    a = ap.parse_args()
    plan, G, V = load()
    today = a.date or datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    day = next((d for d in plan["days"] if d["date"] == today), None)
    if not day:
        print(f"{today}: not in plan range ({plan['start']}..), nothing to send"); return
    batch = next((b for b in day["batches"] if b["slot"] == a.slot), None)
    if not batch:
        print("no batch for this slot"); return
    site = os.environ.get("SITE_URL", "")
    extra = load_full()
    msg = compose(plan, G, V, day, batch, site, extra.get("compare", []))
    if a.dry_run:
        print(msg); print("\n--- audio script ---\n" + audio_script(G, V, batch)[:300]); return
    token, chat = os.environ["TG_TOKEN"].strip(), os.environ["TG_CHAT_ID"].strip()
    _diagnose(token, chat)
    tg(token, "sendMessage", chat_id=chat, text=msg, parse_mode="HTML", disable_web_page_preview="true")
    lid = batch.get("listen")
    if lid:                                          # listening practice: only the clip + a one-line caption
        try:
            sys.path.insert(0, str(ROOT / "scripts"))
            from crypto_bundle import decrypt_blob
            L = next(x for x in extra.get("listening", []) if x["id"] == lid)
            data = decrypt_blob(DATA / "l" / f"{lid}.enc", os.environ["DATA_PASSWORD"])
            tg(token, "sendAudio", chat_id=chat, title=f"聽力 {L['level']}・{L['title']}"[:60], performer="JLPT",
               caption=f"🎧 今日聽力・{L['level']}・{L['title']}\n逐字稿・翻譯・重點請看網頁", files={"audio": (f"{lid}.mp3", data)})
        except Exception as e:
            print("listening skipped:", e, file=sys.stderr)
    if not a.no_audio:
        try:
            with tempfile.TemporaryDirectory() as td:
                p = os.path.join(td, f"day{day['day']}-{a.slot}.mp3")
                asyncio.run(make_mp3(audio_script(G, V, batch), p, day["day"]))
                with open(p, "rb") as f:
                    tg(token, "sendAudio", chat_id=chat, title=f"Day {day['day']} {a.slot}", files={"audio": f})
        except Exception as e:     # audio is a bonus; never fail the digest
            print("audio skipped:", e, file=sys.stderr)


if __name__ == "__main__":
    main()
