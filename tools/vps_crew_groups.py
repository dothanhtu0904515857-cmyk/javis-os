"""Inside the Javis container (cd /app/server): list the Zalo groups the bot sees, with their title and reply mode,
or set groups to "always" (every voice/text there reaches the Agent, no tag needed).

    python3 vps_crew_groups.py <bot_id>                       # list
    python3 vps_crew_groups.py <bot_id> always <group id> ... # set those groups to "always"
"""
import glob
import sqlite3
import sys

sys.path.insert(0, "/app/server")
import chatbot_store  # noqa: E402
import config  # noqa: E402


def titles() -> dict:
    """{chat id: title} from every SQLite table in the state folder that has a chat id and a title column."""
    out = {}
    for db in glob.glob(str(config.STATE_DIR / "*.db")) + glob.glob(str(config.STATE_DIR / "*.sqlite3")):
        try:
            con = sqlite3.connect(db)
            for (t,) in con.execute("select name from sqlite_master where type='table'"):
                cols = [r[1] for r in con.execute(f"pragma table_info('{t}')")]
                cid = next((c for c in ("external_chat_id", "chat_id", "thread_id") if c in cols), None)
                tit = next((c for c in ("chat_title", "title", "name", "display_name") if c in cols), None)
                if not cid or not tit:
                    continue
                for a, b in con.execute(f"select {cid}, {tit} from '{t}' where {tit} is not null and {tit} != ''"):
                    if a and b and str(a) not in out:
                        out[str(a)] = str(b)
        except Exception:      # noqa: BLE001
            continue
    return out


bot_id = sys.argv[1]
if len(sys.argv) > 3 and sys.argv[2] == "always":
    cfg = chatbot_store.get_bot(bot_id) or {}
    gm = dict(cfg.get("group_modes") or {})
    for g in sys.argv[3:]:
        gm[g] = "always"
    ok, err = chatbot_store.update_bot(bot_id, {"group_modes": gm})
    print("SET", ok, err, chatbot_store.get_bot(bot_id).get("group_modes"))
cfg = chatbot_store.get_bot(bot_id) or {}
t = titles()
modes = cfg.get("group_modes") or {}
print("bot", bot_id, "default reply_when:", cfg.get("reply_when"))
for g in cfg.get("groups") or []:
    print(f"  {g}  mode={modes.get(g, cfg.get('reply_when'))}  {t.get(g, '?')}")
for g in modes:
    if g not in (cfg.get("groups") or []):
        print(f"  {g}  mode={modes[g]}  {t.get(g, '?')}  (not in list)")
