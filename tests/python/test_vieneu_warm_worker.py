"""The VieNeu model is loaded ONCE in a worker process and reused for every sentence (fast voice replies, no tokens).

A fake `vieneu` package stands in for the real engine: it counts model loads, prints noise to stdout (as real libraries
do) and writes a small wav. The worker must answer through its protocol despite the noise, reuse one process for many
sentences, and come back after it dies."""
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
import voice_offline as vo

fails = 0


def check(name, cond, info=""):
    global fails
    print(("ok   " if cond else "FAIL ") + name + (f"  [{info}]" if not cond and info else ""))
    fails += 0 if cond else 1


FAKE = '''
import os
print("loading model... 100%")            # noise on stdout: must not break the protocol
open(os.environ["FAKE_LOADS"], "a").write("x")
class Vieneu:
    def __init__(self, **kw):
        self.kw = kw
    def infer(self, text, **kw):
        print("infer progress", text)
        if text == "boom":
            raise ValueError("bad text")
        return (text, kw)
    def save(self, audio, out):
        open(out, "wb").write(b"RIFF" + audio[0].encode("utf-8"))
'''

with tempfile.TemporaryDirectory() as d:
    h = Path(d)
    (h / "vieneu-lib" / "vieneu").mkdir(parents=True)
    (h / "vieneu-lib" / "vieneu" / "__init__.py").write_text(FAKE, encoding="utf-8")
    (h / "hf-w").mkdir()
    (h / "ref_giong.wav").write_bytes(b"R" * 5000)
    loads = h / "loads.txt"
    env = {"FAKE_LOADS": str(loads), "JAVIS_VOICE_CLONE_REF": "", "JAVIS_VIENEU_WARM": "1"}

    async def scenario():
        out = {}
        out["a"] = await vo.speak_vi_clone("Dạ em đây ạ")
        pid1 = vo._W["proc"].pid
        out["b"] = await vo.speak_vi_clone("CREWVN xin chào")
        out["same_pid"] = vo._W["proc"].pid == pid1
        out["boom"] = await vo._speak_warm("boom")
        out["alive_after_error"] = vo._W["proc"] is not None and vo._W["proc"].returncode is None
        vo._W["proc"].kill()
        await asyncio.sleep(0.3)
        out["c"] = await vo.speak_vi_clone("lại nói")
        out["new_pid"] = vo._W["proc"].pid != pid1
        vo._worker_stop()
        return out

    with patch.object(vo, "home", lambda: h), patch.dict(os.environ, env), \
            patch.object(vo, "_to_mp3", lambda wav: b"MP3:" + wav), \
            patch.object(vo, "_vieneu_sync", lambda t: b"ONESHOT"):
        r = asyncio.run(scenario())
    check("first sentence spoken by the warm worker", r["a"] == "MP3:RIFFDạ em đây ạ".encode("utf-8"), r["a"])
    check("company name rewritten before speaking", r["b"] == "MP3:RIFFcờ riu vi en xin chào".encode("utf-8"), r["b"])
    check("the same process serves the next sentence", r["same_pid"])
    check("a bad sentence fails alone", r["boom"] == b"" and r["alive_after_error"])
    check("a dead worker is replaced on the next sentence", r["new_pid"] and r["c"] == "MP3:RIFFlại nói".encode("utf-8"), r["c"])
    check("model loaded once per worker (2 workers = 2 loads)", loads.read_text() == "xx", loads.read_text())

    # worker off: the one-shot process is the backup
    with patch.object(vo, "home", lambda: h), patch.dict(os.environ, dict(env, JAVIS_VIENEU_WARM="0")), \
            patch.object(vo, "_vieneu_sync", lambda t: b"ONESHOT"):
        check("JAVIS_VIENEU_WARM=0 uses the one-shot process", asyncio.run(vo.speak_vi_clone("xin chào")) == b"ONESHOT")

print("ALL PASS" if not fails else f"{fails} FAIL")
sys.exit(1 if fails else 0)
