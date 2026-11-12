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


def _speakable(text: str) -> str:
    """Strip markdown marks and links so the voice never reads out symbols."""
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", str(text or ""))
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"[*_#`>|~]+", "", t)
    return " ".join(t.split())


def _segments(clean: str) -> list:
    """[(text, is_chinese)]: Chinese characters are read by a Chinese voice, the rest by the Vietnamese one.
    A Vietnamese voice skips Hanzi, which would leave holes in the answers of a Chinese-learning group."""
    out = []
    for i, part in enumerate(_HAN.split(clean)):
        if part and part.strip():
            out.append((part.strip(), i % 2 == 1))
    return out or [(clean, False)]


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
    gTTS(text, lang=lang).write_to_fp(buf)
    return buf.getvalue()


async def make_mp3(text: str) -> bytes:
    """Edge TTS first (Hoai My for Vietnamese, Xiaoxiao for Chinese); when Microsoft returns no audio, free Google TTS."""
    clean = _speakable(text)[:MAX_CHARS]
    if not clean:
        raise ValueError("empty voice reply")
    parts = _segments(clean)
    audio = bytearray()
    try:
        for part, zh in parts:
            audio.extend(await _edge(part, VOICE_ZH if zh else VOICE, RATE_ZH if zh else RATE))
    except Exception:
        audio = bytearray()
    if not audio:
        for part, zh in parts:
            audio.extend(await asyncio.to_thread(_gtts_mp3, part, "zh-CN" if zh else "vi"))
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
