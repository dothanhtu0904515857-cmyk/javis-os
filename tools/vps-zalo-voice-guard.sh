#!/usr/bin/env bash
# Keeps the Zalo voice fix alive across Javis updates. Runs from root's cron every 5 minutes on the VPS.
#
# A Javis update (Watchtower or the in-app updater) recreates the container, which throws away files copied into it.
# This guard notices that the fix is gone and applies the fix as a PATCH onto the new version's own files:
#   - the new Javis is healthy and does not have the fix  -> patch the new files, check the syntax, copy them in, restart;
#   - the patch no longer fits (Javis changed those lines) -> change NOTHING and write one WARNING in guard.log;
#   - the fix is already there (re-applied, or merged upstream) -> do nothing.
# It never touches a container that is not healthy, so it cannot race an update in progress.
set -uo pipefail

DIR="${DIR:-/root/javis-patches/zalo-voice}"
LOG="$DIR/guard.log"
FILES="server/channels/zalo_personal.py server/chatbot_runtime.py server/chatbot_store.py server/main.py
server/reminders.py server/voice_note.py server/voice_offline.py server/zalo_audio_reply.py server/zalo_cli.py
server/zalo_personal_channel.py server/zalo_voice_reminder.py server/zalo_voice_tool.py
system/plugins/javis-schedule/plugin.py"
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
dexec() { docker exec "$@" </dev/null; }

CONT="$(docker ps --format '{{.Names}}' | grep -E '^javis' | head -1 || true)"
[ -n "$CONT" ] || exit 0
[ "$(docker inspect -f '{{.State.Health.Status}}' "$CONT" 2>/dev/null)" = "healthy" ] || exit 0

# The fix is there when the voice engine has the warm worker and the Zalo channel starts it.
if dexec "$CONT" grep -q "def warm_soon" /app/server/voice_offline.py 2>/dev/null \
   && dexec "$CONT" grep -q "warm_soon" /app/server/zalo_personal_channel.py 2>/dev/null; then
  exit 0
fi

VER="$(dexec "$CONT" cat /app/VERSION 2>/dev/null | tr -d '[:space:]')"
log "fix missing on Javis $VER, trying to apply the patch"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
BAK="$DIR/backup-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$BAK"
for f in $FILES; do
  mkdir -p "$WORK/$(dirname "$f")" "$BAK/$(dirname "$f")"
  docker cp "$CONT:/app/$f" "$WORK/$f" >/dev/null 2>&1 || true        # new files are not in the container yet
  [ -f "$WORK/$f" ] && cp "$WORK/$f" "$BAK/$f"
done

cd "$WORK" || exit 0
if command -v git >/dev/null 2>&1; then
  APPLY_CHECK="git apply -C1 --check"; APPLY="git apply -C1"
else
  APPLY_CHECK="patch -p1 --dry-run -s -i"; APPLY="patch -p1 -s -i"
fi
if ! $APPLY_CHECK "$DIR/zalo-voice.patch" >/dev/null 2>"$WORK/why.txt"; then
  log "WARNING: the Zalo voice patch does not fit Javis $VER (nothing changed): $(head -c 300 "$WORK/why.txt" | tr '\n' ' ')"
  log "WARNING: ask for the patch to be rebuilt on $VER; backup of the current files is in $BAK"
  exit 0
fi
$APPLY "$DIR/zalo-voice.patch" >/dev/null 2>&1 || { log "WARNING: applying failed, nothing copied"; exit 0; }

for f in $FILES; do
  case "$f" in *.py)
    python3 -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read())" "$WORK/$f" 2>>"$LOG" \
      || { log "WARNING: syntax check failed for $f, nothing copied"; exit 0; } ;;
  esac
done
for f in $FILES; do docker cp "$WORK/$f" "$CONT:/app/$f" >/dev/null || { log "WARNING: copy failed for $f"; exit 1; }; done
docker restart "$CONT" >/dev/null
log "OK: Zalo voice fix applied to Javis $VER (backup $BAK)"
