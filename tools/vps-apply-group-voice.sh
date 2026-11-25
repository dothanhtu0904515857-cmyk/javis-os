#!/usr/bin/env bash
# Applies the "hear group voice messages" fix to the running Javis container on the VPS and keeps it alive across
# Javis updates (root cron every 5 minutes). Run once in the hPanel web console:
#   curl -fsSL https://raw.githubusercontent.com/dothanhtu0904515857-cmyk/javis-os/claude/maritime-docs-javis-vps-issue-2ac159/tools/vps-apply-group-voice.sh | bash
#
# Safe by design: it patches COPIES of the two files, checks the patch fits and the syntax is valid, backs up the
# current files, copies them in, restarts, and puts the backups back if the container does not come back healthy.
# When the patch does not fit (Javis changed those lines) it changes nothing and writes WARNING to guard.log.
set -uo pipefail

DIR=/root/javis-patches/group-voice
RAW=https://raw.githubusercontent.com/dothanhtu0904515857-cmyk/javis-os/claude/maritime-docs-javis-vps-issue-2ac159
FILES="server/chatbot_runtime.py server/zalo_voice_history.py"
LOG="$DIR/guard.log"
mkdir -p "$DIR"
say() { echo "$*"; echo "$(date '+%F %T') $*" >> "$LOG"; }
dexec() { docker exec "$@" </dev/null; }

# First run (piped from curl): keep a copy of this script and install the cron guard.
if [ "${1:-}" != "--cron" ]; then
  curl -fsSL "$RAW/tools/vps-apply-group-voice.sh" -o "$DIR/apply.sh" && chmod +x "$DIR/apply.sh"
  CRON="*/5 * * * * flock -n /tmp/group-voice-guard.lock $DIR/apply.sh --cron"
  ( crontab -l 2>/dev/null | grep -v "group-voice/apply.sh"; echo "$CRON" ) | crontab -
  say "cron guard installed"
fi

CONT="$(docker ps --format '{{.Names}}' | grep -E '^javis' | head -1 || true)"
[ -n "$CONT" ] || { say "no javis container running"; exit 1; }
[ "$(docker inspect -f '{{.State.Health.Status}}' "$CONT" 2>/dev/null)" = "healthy" ] || { say "container not healthy, try later"; exit 1; }

if dexec "$CONT" grep -q "def hear_group_voices" /app/server/chatbot_runtime.py 2>/dev/null; then
  [ "${1:-}" = "--cron" ] || say "fix already present, nothing to do"
  exit 0
fi

# The zalo-voice fix has its own guard; let it finish first so this patch goes on top of the final files.
if ! dexec "$CONT" grep -q "def warm_soon" /app/server/voice_offline.py 2>/dev/null; then
  [ "${1:-}" = "--cron" ] || say "WARNING: zalo-voice fix not present yet; applying on the plain files"
fi

VER="$(dexec "$CONT" cat /app/VERSION 2>/dev/null | tr -d '[:space:]')"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
BAK="$DIR/backup-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$BAK"
curl -fsSL "$RAW/tools/group-voice-context.patch" -o "$DIR/group-voice-context.patch" || { say "cannot download the patch"; exit 1; }

for f in $FILES; do
  mkdir -p "$WORK/$(dirname "$f")" "$BAK/$(dirname "$f")"
  docker cp "$CONT:/app/$f" "$WORK/$f" >/dev/null 2>&1 || { say "cannot read $f from the container"; exit 1; }
  cp "$WORK/$f" "$BAK/$f"
done

cd "$WORK" || exit 1
if ! git apply -C1 --check "$DIR/group-voice-context.patch" 2>"$WORK/why.txt"; then
  say "WARNING: patch does not fit Javis $VER, nothing changed: $(head -c 300 "$WORK/why.txt" | tr '\n' ' ')"
  exit 1
fi
git apply -C1 "$DIR/group-voice-context.patch" || { say "applying failed, nothing copied"; exit 1; }
for f in $FILES; do
  python3 -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read())" "$WORK/$f" \
    || { say "WARNING: syntax check failed for $f, nothing copied"; exit 1; }
done
for f in $FILES; do docker cp "$WORK/$f" "$CONT:/app/$f" >/dev/null || { say "copy failed for $f"; exit 1; }; done
docker restart "$CONT" >/dev/null

for i in $(seq 1 40); do
  sleep 5
  [ "$(docker inspect -f '{{.State.Health.Status}}' "$CONT" 2>/dev/null)" = "healthy" ] && { say "OK: group voice fix applied to Javis $VER (backup $BAK)"; exit 0; }
done
say "WARNING: container not healthy after the patch, putting the backup back"
for f in $FILES; do docker cp "$BAK/$f" "$CONT:/app/$f" >/dev/null; done
docker restart "$CONT" >/dev/null
exit 1
