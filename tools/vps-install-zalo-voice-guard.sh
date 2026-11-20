#!/usr/bin/env bash
# One-time install of the guard that re-applies the Zalo voice fix after every Javis update (run as root on the VPS):
#   curl -fsSL https://raw.githubusercontent.com/dothanhtu0904515857-cmyk/javis-os/<commit>/tools/vps-install-zalo-voice-guard.sh | REF=<commit> bash
set -euo pipefail
REPO="${REPO:-dothanhtu0904515857-cmyk/javis-os}"
REF="${REF:?set REF to the commit that holds the patch}"
DIR=/root/javis-patches/zalo-voice
mkdir -p "$DIR"
command -v git >/dev/null 2>&1 || command -v patch >/dev/null 2>&1 || { apt-get update -q >/dev/null; apt-get install -y -q git >/dev/null; }
for f in zalo-voice.patch vps-zalo-voice-guard.sh; do
  curl -fsSL "https://raw.githubusercontent.com/$REPO/$REF/tools/$f" -o "$DIR/$f.new"
  [ -s "$DIR/$f.new" ] || { echo "Could not download $f"; exit 1; }
  mv "$DIR/$f.new" "$DIR/$f"
done
chmod +x "$DIR/vps-zalo-voice-guard.sh"
LINE="*/5 * * * * $DIR/vps-zalo-voice-guard.sh"
if ! crontab -l 2>/dev/null | grep -qF "$DIR/vps-zalo-voice-guard.sh"; then
  (crontab -l 2>/dev/null || true; echo "$LINE") | crontab -
  echo "Cron entry added: $LINE"
else
  echo "Cron entry already there"
fi
"$DIR/vps-zalo-voice-guard.sh" && echo "Guard ran once (see $DIR/guard.log). Installed."
