"""The Zalo voice reply is read by VieNeu in the owner's cloned voice when it is set up, and falls back when not."""
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
import voice_offline as vo
import zalo_audio_reply as zar

fails = 0


def check(name, cond):
    global fails
    print(("ok   " if cond else "FAIL ") + name)
    fails += 0 if cond else 1


with tempfile.TemporaryDirectory() as d:
    h = Path(d)
    with patch.object(vo, "home", lambda: h), patch.dict(os.environ, {"JAVIS_VOICE_CLONE_REF": ""}):
        check("no reference recording: no clone", vo.clone_ref() is None)
        src = h / "mau.wav"
        src.write_bytes(b"R" * 5000)
        dst = vo.set_clone_ref(str(src))
        check("reference copied into the tts folder", dst == h / "ref_giong.wav" and vo.clone_ref() == dst)
        try:
            vo.set_clone_ref(str(h / "none.wav"))
            check("a missing reference is refused", False)
        except FileNotFoundError:
            check("a missing reference is refused", True)
        check("VieNeu absent: not available", not vo.vieneu_available())
        check("VieNeu absent: speak_vi_clone gives b''", asyncio.run(vo.speak_vi_clone("xin chào")) == b"")
        (h / "pronounce.json").write_text('{"SMCP": "ét em xê pê"}', encoding="utf-8")
        check("company name is spelled out", "cờ riu vi en" in vo.say_words("Chào mừng đến CREWVN"))
        check("pronounce.json is applied", "ét em xê pê" in vo.say_words("học SMCP"))
    with patch.dict(os.environ, {"JAVIS_VOICE_CLONE_REF": str(src)}), patch.object(vo, "home", lambda: h):
        (h / "ref_giong.wav").unlink()
        check("JAVIS_VOICE_CLONE_REF is honoured", vo.clone_ref() == src)

# make_mp3: Vietnamese comes from VieNeu, English from Google, joined; and a VieNeu failure falls back
async def fake_clone(t):
    return b"VIENEU"


async def no_clone(t):
    return b""


def fake_gtts(t, lang):
    return b"G-" + lang.encode()


with patch.object(zar, "_gtts_mp3", fake_gtts), patch.object(vo, "_concat", lambda parts: b"|".join(parts)):
    with patch.object(vo, "speak_vi_clone", fake_clone):
        out = asyncio.run(zar.make_mp3("Dạ em đây ạ. Lower the lifeboat now!"))
        check("Vietnamese by VieNeu, English by Google, joined", out == b"VIENEU|G-en")
    with patch.object(vo, "speak_vi_clone", no_clone):
        out = asyncio.run(zar.make_mp3("Dạ em đây ạ."))
        check("VieNeu gives nothing: Google reads it", out == b"G-vi")

print("ALL PASS" if not fails else f"{fails} FAIL")
sys.exit(1 if fails else 0)
