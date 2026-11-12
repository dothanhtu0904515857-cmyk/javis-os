"""Personal Zalo: the bot HEARS voice messages in groups and ANSWERS BY VOICE.

    python tests/run.py zalo_group_voice      (no network, no real Zalo, fake MCP, fake engine)

Request 12/11/2026 ("Nhóm tiếng Tàu"): a member sent a voice message, then "@Crew nhận xét e ơi"; the bot said it could not
hear it. Two gaps, locked here:
  1. A bare voice message in a GROUP was dropped (only private chats heard voice). Now it is remembered per sender and
     heard when the SAME person next calls the bot; a voice that replies to the bot is answered at once; nobody else's voice
     is used; it is used once.
  2. The voice reply (`voice_reply: audio_file`) had lost its wiring in an update. Now: an answer to a voice message is
     spoken; otherwise only bots with `voice_reply` speak (private always, a group only when asked); the mp3 goes out
     through the stock `zalo_send_file` tool; the echo of that file is not mistaken for the owner typing.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-group-voice-")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import chatbot_runtime  # noqa: E402
import chatbot_store  # noqa: E402
import zalo_audio_reply as za  # noqa: E402
import zalo_cli  # noqa: E402
import zalo_personal_channel as zc  # noqa: E402
from channels import zalo_personal as zp  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else f"  [{str(detail)[:400]}]"))
    if not cond:
        fails.append(name)


CID = "zalo-vn"
GROUP = "2000000009"
LAN, MINH = "1000000001", "1000000002"
URL = "https://voice.example.zalo/v1.aac"
METAS, SPOKEN, TEXTS = [], [], []
CALL = {"tag": False, "rep": False}


async def fake_goi(conn, tool, args):
    return {}


zc.ket_noi_theo_id = lambda cid: {"id": CID, "label": "Crew"} if cid == CID else None
zc._goi = fake_goi
zc.nhan_dien_goi = lambda cid, ev, names: (CALL["tag"], CALL["rep"])


async def answer(text, meta, _p):
    METAS.append((text, dict(meta)))
    return {"text": "Dạ em nghe rồi ạ", "files": []}


def make_bot(cfg):
    t = zp.Transport(CID, [], answer, cfg_fn=lambda: cfg)
    zc._BOTS[CID] = t

    async def fake_send(thread, cau, chat_type="private", meta=None, receipt_row=0):
        TEXTS.append(cau)
        return True

    async def fake_voice(thread, cau, chat_type="private"):
        SPOKEN.append((thread, cau, chat_type))
        return True
    t._gui, t._send_voice = fake_send, fake_voice
    return t


def ev(kind="text", sender=LAN, text="", mid=None, **md):
    return {"chat_type": "group", "message_type": kind, "text": text, "external_chat_id": GROUP,
            "external_message_id": mid or f"m{time.time_ns()}", "sender_id": sender, "sender_name": "Đức",
            "sender_type": "customer", "account_id": CID, "created_at": time.time(), "metadata": dict(md)}


def reset():
    METAS.clear(); SPOKEN.clear(); TEXTS.clear()
    zp._GROUP_VOICE.clear()
    CALL.update(tag=False, rep=False)


CFG = {"id": "bot-vn", "reply_when": "always", "voice_reply": "audio_file"}

# ============================================================
# 1. group voice: remembered, then heard when the same person calls the bot
# ============================================================
reset()
t = make_bot(dict(CFG))
asyncio.run(t.xu_ly(ev("audio", audio_url=URL)))
check("a bare group voice is not answered", not METAS and not TEXTS, (METAS, TEXTS))
check("but it is remembered for its sender", (CID, GROUP, LAN) in zp._GROUP_VOICE, zp._GROUP_VOICE)

CALL["tag"] = True
asyncio.run(t.xu_ly(ev("text", text="@Crew nhận xét e ơi")))
check("the tagged text that follows carries the voice link", METAS and METAS[-1][1].get("audio_urls") == [URL], METAS)
check("the voice is used up", (CID, GROUP, LAN) not in zp._GROUP_VOICE)
check("an answer to a voice message is spoken (even in a group)", SPOKEN and SPOKEN[-1][1] == "Dạ em nghe rồi ạ", SPOKEN)
check("the text answer goes out too", TEXTS == ["Dạ em nghe rồi ạ"], TEXTS)

METAS.clear(); SPOKEN.clear()
asyncio.run(t.xu_ly(ev("text", text="@Crew cảm ơn")))
check("used once: the next call has no voice", METAS and not METAS[-1][1].get("audio_urls"), METAS)
check("and a plain group answer is not spoken", not SPOKEN, SPOKEN)

reset()
asyncio.run(t.xu_ly(ev("audio", sender=MINH, audio_url=URL)))
CALL["tag"] = True
asyncio.run(t.xu_ly(ev("text", sender=LAN, text="@Crew nghe giúp em")))
check("CANARY: another member's voice is never attached", METAS and not METAS[-1][1].get("audio_urls"), METAS)

reset()
CALL["tag"] = False
asyncio.run(t.xu_ly(ev("text", text="tsang cai")))
check("an uncalled text attaches nothing (voice stays for the call)", not METAS or not METAS[-1][1].get("audio_urls"), METAS)

reset()
CALL["rep"] = True
asyncio.run(t.xu_ly(ev("audio", audio_url=URL)))
check("a group voice that replies to the bot is answered at once, heard",
      METAS and METAS[-1][1].get("audio_urls") == [URL] and METAS[-1][0] == chatbot_runtime.AUDIO_TRON, METAS)
check("and the answer is spoken", SPOKEN, SPOKEN)

reset()
old = time.time
zp._GROUP_VOICE[(CID, GROUP, LAN)] = (URL, time.time() - zp.GROUP_VOICE_TTL - 5)
CALL["tag"] = True
asyncio.run(t.xu_ly(ev("text", text="@Crew nhận xét")))
check("a voice older than the window is ignored", METAS and not METAS[-1][1].get("audio_urls"), METAS)

# ============================================================
# 2. when does the bot speak
# ============================================================
t_on = zp.Transport(CID, [], answer, cfg_fn=lambda: {"voice_reply": "audio_file"})
t_off = zp.Transport(CID, [], answer, cfg_fn=lambda: {"voice_reply": "off"})
check("voice reply on: every private answer", t_on._wants_voice({"chat_type": "private"}, "giá bao nhiêu"))
check("voice reply on: a group answer only when asked", not t_on._wants_voice({"chat_type": "group"}, "giá bao nhiêu"))
check("voice reply on: group asker wants to hear it", t_on._wants_voice({"chat_type": "group"}, "đọc cho em nghe với"))
check("voice reply off: nothing spoken", not t_off._wants_voice({"chat_type": "private"}, "giá bao nhiêu"))
check("a voice message is always answered by voice, even with the switch off",
      t_off._wants_voice({"chat_type": "group", "audio_urls": [URL]}, ""))

# ============================================================
# 3. the setting survives the store, the mp3 goes through zalo_send_file, the echo is not "the owner typing"
# ============================================================
bid, err = chatbot_store.create_bot({"name": "Crew", "agent_slug": "tro-ly", "brain": "b", "channel": "zalo_personal",
                                     "voice_reply": "audio_file"})
check("create keeps voice_reply", not err and chatbot_store.get_bot(bid).get("voice_reply") == "audio_file", err)
chatbot_store.update_bot(bid, {"voice_reply": "off"})
check("update switches it off", chatbot_store.get_bot(bid).get("voice_reply") == "off")
chatbot_store.update_bot(bid, {"voice_reply": "rubbish"})
check("a bad value is ignored", chatbot_store.get_bot(bid).get("voice_reply") == "off")
check("an old record reads as off", chatbot_store._public({"id": "x"}).get("voice_reply") == "off")

segs = za._segments("Dạ anh, chữ 早上好 đọc là zǎoshang hǎo ạ.")
check("Chinese runs are split out for the Chinese voice", [s for s in segs if s[1]] == [("早上好", True)] and len(segs) == 3, segs)
check("pure Vietnamese stays one piece", za._segments("Dạ anh Đức") == [("Dạ anh Đức", False)])

SENT_FILES = []


async def fake_send_files(conn_id, home, thread_id, files, thread_type=0, caption=""):
    SENT_FILES.append((conn_id, home, thread_id, [Path(f).name for f in files], [Path(f).read_bytes() for f in files], thread_type))
    return True, {"success": True}, ""


async def fake_mp3(text):
    return b"ID3-fake-mp3"


zalo_cli.send_files = fake_send_files
za.make_mp3 = fake_mp3
ok, why = asyncio.run(za.send_audio_file({"id": CID, "env": {"HOME": "/h"}}, GROUP, "group", "Dạ em nghe rồi ạ"))
check("the voice goes through zalo_send_file (group = threadType 1)",
      ok and SENT_FILES and SENT_FILES[0][2:4] == (GROUP, ["Tra loi bang giong noi.mp3"]) and SENT_FILES[0][5] == 1
      and SENT_FILES[0][4] == [b"ID3-fake-mp3"], (ok, why, SENT_FILES))

zc._DA_GUI_ANH.clear()
zc.ghi_da_gui_anh(CID, GROUP, 1)
check("echo of the bot's own mp3 (a file message) is recognised", zc._la_vong_anh(CID, GROUP) is True)

print()
print("FAILED: " + ", ".join(fails) if fails else "all ok")
sys.exit(1 if fails else 0)
