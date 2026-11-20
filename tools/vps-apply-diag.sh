#!/usr/bin/env bash
# Adds the "why was this group message not answered" log lines to the Zalo voice fix already running on a VPS
# (container files = the fix at commit 337a022c). Applies a small patch onto the container's own files, with a backup.
#   curl -fsSL https://raw.githubusercontent.com/<repo>/<commit>/tools/vps-apply-diag.sh | REF=<commit> bash
set -euo pipefail
REPO="${REPO:-dothanhtu0904515857-cmyk/javis-os}"
REF="${REF:?set REF}"
FILES="server/channels/zalo_personal.py server/chatbot_runtime.py"
CONT="${CONT:-$(docker ps --format '{{.Names}}' | grep -E '^javis' | head -1 || true)}"
[ -n "$CONT" ] || { echo "no javis container"; exit 1; }
dexec() { docker exec "$@" </dev/null; }
W="$(mktemp -d)"; B="/root/javis-backup-diag-$(date +%H%M%S)"; mkdir -p "$B"
for f in $FILES; do
  mkdir -p "$W/$(dirname "$f")" "$B/$(dirname "$f")"
  docker cp "$CONT:/app/$f" "$W/$f" >/dev/null; cp "$W/$f" "$B/$f"
done
curl -fsSL "https://raw.githubusercontent.com/$REPO/$REF/tools/zalo-voice-diag.patch" -o "$W/p.patch"
cd "$W"
if command -v git >/dev/null 2>&1; then git apply -C1 --check p.patch && git apply -C1 p.patch
else patch -p1 --dry-run -s -i p.patch && patch -p1 -s -i p.patch; fi
for f in $FILES; do python3 -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read())" "$W/$f"; done
for f in $FILES; do docker cp "$W/$f" "$CONT:/app/$f" >/dev/null; done
docker restart "$CONT" >/dev/null
echo "DIAG_APPLIED backup=$B"
