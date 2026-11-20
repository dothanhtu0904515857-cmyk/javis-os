#!/usr/bin/env bash
# Put the Zalo voice fixes (hear group voice, answer a voice by voice in the cloned VieNeu voice) into the running
# Javis container of a VPS, without waiting for a release. Run as root ON THE VPS:
#
#   curl -fsSL https://raw.githubusercontent.com/dothanhtu0904515857-cmyk/javis-os/claude/command-no-response-2c76eb/tools/vps-apply-zalo-voice.sh | bash
#
# Safe by design: it only proceeds on the Javis version these files were made for, backs up every file it replaces,
# syntax-checks the new files and puts the backup back if anything fails. A container that is recreated (an update)
# loses these files; the fix is permanent once the pull request is in a release.
set -euo pipefail

REPO="${REPO:-dothanhtu0904515857-cmyk/javis-os}"
REF="${REF:-claude/command-no-response-2c76eb}"
WANT_VERSION="0.606.0 or 0.603.0"
FILES="server/channels/zalo_personal.py server/chatbot_runtime.py server/chatbot_store.py server/main.py
server/reminders.py server/voice_note.py server/voice_offline.py server/zalo_audio_reply.py server/zalo_cli.py
server/zalo_personal_channel.py server/zalo_voice_reminder.py server/zalo_voice_tool.py
system/plugins/javis-schedule/plugin.py"

CONT="${CONT:-$(docker ps --format '{{.Names}}' | grep -E '^javis' | head -1 || true)}"
[ -n "$CONT" ] || { echo "No running container whose name starts with 'javis'. Set CONT=<name>."; exit 1; }
VER="$(docker exec "$CONT" cat /app/VERSION | tr -d '[:space:]')"
echo "Container: $CONT, Javis version: $VER"
# Only server/main.py differs between 0.603.0 and 0.606.0 among these files; 0.603.0 gets its own main.py (the 0.603.0
# one plus the same changes), kept on the branch `vps-compat-0.603.0`.
MAIN_URL_REF="$REF"; MAIN_URL_PATH="server/main.py"
case "$VER" in
  0.606.0) ;;
  0.603.0) MAIN_URL_REF="vps-compat-0.603.0"; MAIN_URL_PATH="main.py" ;;
  *) if [ "${FORCE:-0}" != "1" ]; then
       echo "These files are made for Javis $WANT_VERSION but the container runs $VER. Nothing changed."
       echo "(FORCE=1 applies them anyway, which can break a different Javis.)"
       exit 2
     fi ;;
esac

NEW_LIST="server/voice_offline.py server/zalo_audio_reply.py server/zalo_voice_reminder.py server/zalo_voice_tool.py"
WORK="$(mktemp -d)"; BAK="/root/javis-backup-zalo-voice-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BAK" "$WORK"
for f in $FILES; do
  mkdir -p "$WORK/$(dirname "$f")" "$BAK/$(dirname "$f")"
  if [ "$f" = "server/main.py" ]; then src="$MAIN_URL_REF/$MAIN_URL_PATH"; else src="$REF/$f"; fi
  curl -fsSL "https://raw.githubusercontent.com/$REPO/$src" -o "$WORK/$f"
  [ -s "$WORK/$f" ] || { echo "Could not download $f"; exit 1; }
  # A file that is new in this fix is not in the container yet: nothing to back up, and undoing means deleting it.
  if echo " $NEW_LIST " | grep -q " $f "; then echo "$f" >> "$BAK/NEW_FILES"; else docker cp "$CONT:/app/$f" "$BAK/$f" >/dev/null; fi
done
touch "$BAK/NEW_FILES"
echo "Backup of the current files: $BAK ($(wc -l < "$BAK/NEW_FILES") file(s) are new)"

restore() {
  echo "Putting the old files back..."
  for f in $FILES; do
    if grep -qx "$f" "$BAK/NEW_FILES"; then docker exec -u root "$CONT" rm -f "/app/$f" || true; else docker cp "$BAK/$f" "$CONT:/app/$f" || true; fi
  done
  docker restart "$CONT" >/dev/null
}

for f in $FILES; do docker cp "$WORK/$f" "$CONT:/app/$f"; done
for f in $FILES; do
  case "$f" in *.py) docker exec "$CONT" python -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read())" "/app/$f" || { echo "Syntax check failed: $f"; restore; exit 1; };; esac
done

# The old host guard re-applies OLDER Zalo patches after updates; these files already include them.
if crontab -l 2>/dev/null | grep -q javis-reapply; then
  crontab -l > "$BAK/crontab.txt"
  crontab -l | grep -v javis-reapply | crontab -
  echo "Old patch guard (javis-reapply) switched off; crontab backup in $BAK/crontab.txt"
fi

# The voice to clone: the reference recording from the Marketing brain, copied next to the voice engine.
docker exec -u root "$CONT" sh -c '
  d=/data/state/tts; mkdir -p "$d"
  if [ -s "$d/ref_giong.wav" ]; then echo "Reference voice already set: $d/ref_giong.wav"; exit 0; fi
  f=$(find /data -name ref_giong_sach.wav -not -path "*/state/tts/*" 2>/dev/null | head -1)
  if [ -n "$f" ]; then cp "$f" "$d/ref_giong.wav" && echo "Reference voice set from $f"
  else echo "WARNING: ref_giong_sach.wav not found; replies use the preset VieNeu voice until you put it in $d/ref_giong.wav"; fi
'

docker restart "$CONT" >/dev/null
echo -n "Waiting for Javis"
for i in $(seq 1 40); do
  if docker exec "$CONT" python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.getenv('JAVIS_PORT','7777')+'/health',timeout=4).status==200 else 1)" 2>/dev/null; then
    echo " ... up."; echo "Done. Send a voice message to the bot in a Zalo group (reply to it or tag it)."
    echo "To undo: copy the files in $BAK back with docker cp (the ones listed in $BAK/NEW_FILES are simply deleted), then docker restart $CONT"
    exit 0
  fi
  echo -n "."; sleep 3
done
echo; echo "Javis did not come back in 2 minutes; restoring."; restore; exit 1
