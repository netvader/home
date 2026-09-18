#!/usr/bin/env bash
# Installs these ported apps onto a Tufty2350 in disk mode, without the
# macOS Finder/cp AppleDouble ("._*") junk files that break the on-device
# menu's PNG loader (see README.md).
#
# Usage:
#   ./install.sh [volume] [app ...]
#
#   volume   Mount point of the badge in disk mode. Defaults to /Volumes/TUFTY.
#   app...   Which app folders to install. Defaults to all of them.
#
# Examples:
#   ./install.sh                              # install everything to /Volumes/TUFTY
#   ./install.sh /Volumes/TUFTY badge flappy   # install just two apps
#   ./install.sh /Volumes/BADGER               # different volume name

set -euo pipefail

# This is the actual fix: COPYFILE_DISABLE=1 stops cp(1) (and Finder) from
# writing macOS extended-attribute/resource-fork sidecar files (._foo) next
# to every file it copies onto a non-HFS+ volume like the badge's FAT32/
# exFAT filesystem.
export COPYFILE_DISABLE=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VOLUME="${1:-/Volumes/TUFTY}"
shift || true

if [ ! -d "$VOLUME" ]; then
    echo "error: '$VOLUME' not found - is the badge in disk mode (double-tap RESET)?" >&2
    exit 1
fi

ALL_APPS=(badge commits copilot-loop crypto files flappy gallery gitris hello invaders jezzball life monapet sketch snake stocks weather wifi wled)
APPS=("$@")
if [ "${#APPS[@]}" -eq 0 ]; then
    APPS=("${ALL_APPS[@]}")
fi

mkdir -p "$VOLUME/apps"

for app in "${APPS[@]}"; do
    src="$SCRIPT_DIR/$app"
    if [ ! -d "$src" ]; then
        echo "warning: no such app folder '$app', skipping" >&2
        continue
    fi
    dest="$VOLUME/apps/$app"
    rm -rf "$dest"
    cp -R "$src" "$dest"
    echo "installed $app"
done

if [ ! -f "$VOLUME/secrets.py" ]; then
    cp "$SCRIPT_DIR/secrets.py" "$VOLUME/secrets.py"
    echo "installed secrets.py template - edit it with your Wi-Fi/GitHub details"
fi

# Belt-and-braces: sweep up any AppleDouble files this run still produced
# (e.g. from a stray Finder window open on the volume at the same time),
# or left over from an earlier manual copy.
found=$(find "$VOLUME" -name '._*' -print -delete)
if [ -n "$found" ]; then
    echo "removed leftover AppleDouble files:"
    echo "$found"
fi

echo "done - eject '$VOLUME' and tap RESET once to reboot."
