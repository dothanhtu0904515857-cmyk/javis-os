"""Voice messages sent in a group WITHOUT tagging the bot are heard when a later message tags it (2026-11-25).

    python tests/run.py group_voice_context      (no network, fake ear)

Field report: a teacher sent two voice messages in a group, the owner then tagged the bot with typed words, and the
bot answered that it could not hear them: only the tagged message was ever heard and the group context carried text only.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-gvoice-test-")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import chatbot_runtime  # noqa: E402
import conversations  # noqa: E402
import zalo_attachments  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(extra) + "]") if extra and not cond else ""))
    if not cond:
        fails.append(name)


NOW = time.time()
GR = "group-voice"
heard_calls = []
fetched = []


def add(i, text, kind="text", url="", mid=None, name="Duc"):
    md = {"audio_url": url} if url else {}
    return conversations.ghi_su_kien({
        "channel": "zalo_personal", "account_id": "zp1", "account_name": "Nick", "bot_id": "",
        "external_chat_id": GR, "chat_type": "group", "chat_title": "Group", "sender_type": "customer",
        "sender_id": "u1", "sender_name": name, "message_type": kind, "text": text,
        "external_message_id": mid or f"{GR}-{i}", "created_at": NOW - 1000 + i, "metadata": md})


async def fake_fetch(att, folder, cap):
    fetched.append(att["url"])
    p = Path(folder) / "v.m4a"
    p.write_bytes(b"x")
    return str(p), ""


async def fake_ear(data, name="", agent=None):
    heard_calls.append(name)
    n = len(heard_calls)
    return {"ok": True, "text": f"say number {n} <b>"}


zalo_attachments.fetch_file = fake_fetch
def wire(ear):
    chatbot_runtime.wire(answer=lambda *a, **k: None, brain_root=lambda b: tempfile.gettempdir(),
                         read_agent=lambda br, slug: ({}, ""), transcribe=ear)


wire(fake_ear)

add(1, "hello")
add(2, "https://voice-aac.zdn.vn/a.aac", "audio", "https://voice-aac.zdn.vn/a.aac")
add(3, "https://voice-aac.zdn.vn/b.aac", "audio", "https://voice-aac.zdn.vn/b.aac")
add(4, "@Crew he did not answer", mid="asking")

meta = {"chat_type": "group", "chat_id": GR, "message_id": "asking", "user_name": "Boss"}
voices = asyncio.run(chatbot_runtime.hear_group_voices(meta, "zalo_personal", "zp1", {}))
check("both untagged voice messages are heard", len(voices) == 2 and len(heard_calls) == 2, voices)

meta["_group_voices"] = voices
ctx = chatbot_runtime.ngu_canh_nhom(meta, "zalo_personal", "zp1")
check("context shows what each voice message said", "machine transcript" in ctx and "say number 1" in ctx and "say number 2" in ctx, ctx)
check("angle brackets in a transcript cannot open a tag", "<b>" not in ctx, ctx)
check("the asking message is not in its own context", "did not answer" not in ctx, ctx)

voices2 = asyncio.run(chatbot_runtime.hear_group_voices(meta, "zalo_personal", "zp1", {}))
check("a second turn reuses the cached transcripts (no new hearing)", voices2 == voices and len(heard_calls) == 2, heard_calls)

meta_own = dict(meta, audio_urls=["https://voice-aac.zdn.vn/b.aac"])
meta_own.pop("_group_voices")
check("a voice message the turn itself carries is left to nghe_cho_bot",
      "https://voice-aac.zdn.vn/b.aac" not in asyncio.run(chatbot_runtime.hear_group_voices(meta_own, "zalo_personal", "zp1", {})))

for i in range(10, 16):
    add(i, f"https://voice-aac.zdn.vn/n{i}.aac", "audio", f"https://voice-aac.zdn.vn/n{i}.aac")
before = len(heard_calls)
many = asyncio.run(chatbot_runtime.hear_group_voices(meta_own, "zalo_personal", "zp1", {}))
check("at most GROUP_VOICE_MAX new messages are heard per turn", len(heard_calls) - before <= chatbot_runtime.GROUP_VOICE_MAX, len(heard_calls) - before)

wire(None)
meta2 = {"chat_type": "group", "chat_id": GR, "message_id": "asking"}
check("no ear and nothing cached: no crash, unheard marker in context",
      "could not be heard" in chatbot_runtime.ngu_canh_nhom(dict(meta2, _group_voices={}), "zalo_personal", "zp1")
      and asyncio.run(chatbot_runtime.hear_group_voices({"chat_type": "private", "chat_id": GR}, "zalo_personal", "zp1", {})) == {})

if fails:
    print("\nFAIL - test_group_voice_context: " + ", ".join(fails))
    sys.exit(1)
print("\nOK - test_group_voice_context")
