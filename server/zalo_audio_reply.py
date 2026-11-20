"""Spoken replies on personal Zalo: turn the bot's answer into an mp3 and send it into the chat.

The mp3 goes out as a playable file through the stock MCP tool `zalo_send_file` (`zalo_cli.send_files`), on the MCP
process that already holds the Zalo session. Zalo's native voice bubble needs a public URL for the recording, and a
customer's answer is never published, so the file path is the one used.
"""
from __future__ import annotations

import asyncio
import re
import tempfile
import unicodedata
from pathlib import Path

VOICE = "vi-VN-HoaiMyNeural"
RATE = "-10%"
VOICE_ZH = "zh-CN-XiaoxiaoNeural"
RATE_ZH = "-20%"        # slower for learners
MAX_CHARS = 700
FILE_NAME = "Tra loi bang giong noi.mp3"

# What an asker writes when they want to hear the answer, compared after stripping accents (people type without them).
_VOICE_REQUESTS = ("tin nhan thoai", "nhan thoai", "giong noi", "am thanh", "voice", "audio",
                   "ghi am", "doc cho", "noi cho", "cho nghe", "bang giong")
_HAN = re.compile(r"([㐀-鿿豈-﫿]+(?:[\s，。！？、：；,.!?]*[㐀-鿿豈-﫿]+)*)")


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower()).replace("đ", "d")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def asks_for_voice(text: str) -> bool:
    """True when the asker wants a spoken reply (gates voice replies in group chats)."""
    t = _strip_accents(text)
    return any(k in t for k in _VOICE_REQUESTS)


_VOICE_BLOCK = re.compile(r"<voice>(.*?)</voice>", re.S | re.I)


def split_voice(answer: str) -> tuple:
    """(text to write, text to say). An answer may carry `<voice>...</voice>`: that part is spoken, the rest is written.
    No tag: nothing is split and the whole answer is both written and spoken, as before."""
    spoken = " ".join(" ".join(m.split()) for m in _VOICE_BLOCK.findall(str(answer or ""))).strip()
    written = re.sub(r"\n{3,}", "\n\n", _VOICE_BLOCK.sub("", str(answer or ""))).strip()
    return written, spoken


def _speakable(text: str) -> str:
    """Strip markdown marks and links so the voice never reads out symbols."""
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", str(text or ""))
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[*_#`>|~]+", "", t)
    return " ".join(t.split())


_VI_ONLY = set("ăâêôơưđạảãấầẩẫậắằẳẵặẹẻẽếềểễệịỉĩọỏõốồổỗộớờởỡợụủũứừửữựỳỵỷỹý")
_PINYIN_SURE = set("āēīōūǖǎěǐǒǔǚǘǜ")           # macron / caron: never Vietnamese
_PINYIN_WORD = re.compile(r"^[a-zàáèéìíòóùúüāēīōūǖǎěǐǒǔǚǘǜ']+$")
_SENTENCE = re.compile(r"(?<=[.!?;:])\s+")
MAX_SEGMENTS = 14
SLOW_ZH_CHARS = 12        # a short Chinese piece is a word being taught: read it slowly


def _han_lang(part: str) -> str:
    """zh-TW for traditional characters (they do not fit the simplified GB2312 set), zh-CN otherwise."""
    han = "".join(c for c in part if "㐀" <= c <= "鿿")
    try:
        han.encode("gb2312")
        return "zh-CN"
    except UnicodeEncodeError:
        try:
            han.encode("big5")
            return "zh-TW"
        except UnicodeEncodeError:
            return "zh-CN"


def _drop_pinyin(text: str) -> str:
    """Remove pinyin runs ("zǎoshang hǎo") from text that sits next to the Hanzi they spell: the Chinese voice already
    says the characters correctly, and a Vietnamese voice reading pinyin letters teaches a wrong pronunciation."""
    words = text.split(" ")
    low = [w.strip("()[]\"'“”,.;:!?/").lower() for w in words]
    sure = [bool(w) and any(c in _PINYIN_SURE for c in w) and not any(c in _VI_ONLY for c in w) for w in low]
    drop = list(sure)
    for step in (1, -1):                      # tone-marked neighbours of a sure pinyin word belong to the same run
        rng = range(len(words)) if step == 1 else range(len(words) - 1, -1, -1)
        for i in rng:
            j = i - step
            if (not drop[i] and 0 <= j < len(words) and drop[j] and low[i] and _PINYIN_WORD.match(low[i])
                    and not any(c in _VI_ONLY for c in low[i]) and any(c in "àáèéìíòóùú" for c in low[i])):
                drop[i] = True
    return " ".join(w for w, d in zip(words, drop) if not d)


def _latin_lang(sentence: str) -> str:
    """vi when the sentence carries any Vietnamese letter; en for a plain-ASCII sentence of two words or more."""
    low = sentence.lower()
    if any(c in _VI_ONLY or c in "àáèéìíòóùú" for c in low):
        return "vi"
    return "en" if len(re.findall(r"[a-z]{2,}", low)) >= 2 else "vi"


def _segments(clean: str) -> list:
    """[(text, lang)] with lang one of vi, en, zh-CN, zh-TW: each piece is read by the Google voice of its own language.
    A Vietnamese voice skips Hanzi and mangles English, which leaves holes in a trilingual (Viet-English-Chinese) answer."""
    has_han = bool(_HAN.search(clean))
    out = []
    for i, part in enumerate(_HAN.split(clean)):
        if not part or not part.strip():
            continue
        if i % 2 == 1:
            out.append((part.strip(), _han_lang(part)))
            continue
        if has_han:
            part = _drop_pinyin(part)
        for sentence in _SENTENCE.split(part):
            s = sentence.strip(" ()[]-,")
            if re.search(r"\w", s):
                out.append((s, _latin_lang(s)))
    merged = []
    for text, lang in out:
        if merged and merged[-1][1] == lang and not lang.startswith("zh"):
            merged[-1] = (merged[-1][0] + " " + text, lang)
        else:
            merged.append((text, lang))
    return merged[:MAX_SEGMENTS] or [(clean, "vi")]


async def _edge(text: str, voice: str, rate: str) -> bytes:
    import edge_tts

    audio = bytearray()
    async for chunk in edge_tts.Communicate(text, voice, rate=rate).stream():
        if chunk.get("type") == "audio":
            audio.extend(chunk.get("data") or b"")
    return bytes(audio)


def _gtts_mp3(text: str, lang: str) -> bytes:
    import io
    from gtts import gTTS

    buf = io.BytesIO()
    slow = lang.startswith("zh") and len(text) <= SLOW_ZH_CHARS
    gTTS(text, lang=lang, slow=slow).write_to_fp(buf)
    return buf.getvalue()


_EDGE_VOICES = {"vi": (VOICE, RATE), "en": ("en-US-AriaNeural", "-10%"),
                "zh-CN": (VOICE_ZH, RATE_ZH), "zh-TW": ("zh-TW-HsiaoChenNeural", RATE_ZH)}


async def make_mp3(text: str) -> bytes:
    """Google Translate's TTS first (owner's choice, 2026-11-12: its Mandarin follows the standard pinyin reading), one
    voice per language piece (vi, en, zh-CN, zh-TW); Edge TTS voices when Google returns no audio."""
    clean = _speakable(text)[:MAX_CHARS]
    if not clean:
        raise ValueError("empty voice reply")
    parts = _segments(clean)
    # Vietnamese pieces are read by VieNeu (the owner's cloned voice when its reference recording is set up, see
    # `voice_offline.clone_ref`): no tokens, no internet. English and Chinese pieces keep their own voices. Anything
    # VieNeu cannot do falls through to the online voices below.
    audio = bytearray()
    try:
        import voice_offline
        pieces, used_clone = [], False
        for part, lang in parts:
            b = await voice_offline.speak_vi_clone(part) if lang == "vi" else b""
            used_clone = used_clone or bool(b)
            pieces.append(b or await asyncio.to_thread(_gtts_mp3, part, lang))
        if used_clone:
            # Pieces come from engines with different sample rates: join them properly, not byte by byte.
            joined = await asyncio.to_thread(voice_offline._concat, pieces) if len(pieces) > 1 else pieces[0]
            audio.extend(joined or b"".join(pieces))
        else:
            audio.extend(b"".join(pieces))
    except Exception:
        audio = bytearray()
    if not audio:
        try:
            for part, lang in parts:
                audio.extend(await asyncio.to_thread(_gtts_mp3, part, lang))
        except Exception:
            audio = bytearray()
    if not audio:
        for part, lang in parts:
            voice, rate = _EDGE_VOICES[lang]
            audio.extend(await _edge(part, voice, rate))
    if not audio:
        raise RuntimeError("text to speech returned no audio")
    return bytes(audio)


async def send_audio_file(conn: dict, thread_id: str, chat_type: str, text: str) -> tuple[bool, str]:
    """Speak `text` and send the mp3. Returns the real send result; the recording is deleted right after."""
    import zalo_cli

    try:
        home = zalo_cli.home_of(conn)
        if not home:
            return False, "no Zalo session folder"
        audio = await make_mp3(text)
        with tempfile.TemporaryDirectory(prefix="javis-zalo-audio-") as tmp:
            path = Path(tmp) / FILE_NAME
            path.write_bytes(audio)
            ok, _data, err = await zalo_cli.send_files(str(conn.get("id") or ""), home, str(thread_id), [path],
                                                       1 if chat_type == "group" else 0)
        return (True, "") if ok else (False, str(err or "MCP did not confirm")[:300])
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
