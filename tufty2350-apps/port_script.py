#!/usr/bin/env python3
"""Mechanical port of badge25 (GitHub Universe 2025 / badgeware.io API)
apps to the current Pimoroni tufty2350 firmware (v3.1.0) Badgeware API.

Handles the well-established, unambiguous renames. Anything else is left
for manual review and flagged in the output.
"""
import re
import sys
from pathlib import Path

SIMPLE_RENAMES = [
    (r"\bio\.ticks_delta\b", "badge.ticks_delta"),
    (r"\bio\.ticks\b", "badge.ticks"),
    (r"\bbrushes\.color\b", "color.rgb"),
    (r"\bscreen\.brush\b", "screen.pen"),
    (r"\.brush\s*=\s*", ".pen = "),
    (r"\bshapes\.", "shape."),
    (r"\bMatrix\(\)", "mat3()"),
    (r"\bMatrix\b(?=\()", "mat3"),
    (r"\bImage\.load\b", "image.load"),
    (r"\bImage\(", "image("),
    (r"\bPixelFont\.load\b", "font.load"),
]

BUTTON_STATE_RE = re.compile(
    r"\b(?:io\.)?(BUTTON_\w+)\s+in\s+io\.(pressed|held|released|changed)\b"
)

BARE_BUTTON_RE = re.compile(r"\bio\.(BUTTON_\w+)\b")

DRAW_CALL_RE = re.compile(r"\bscreen\.draw\(")

IMPORT_BADGEWARE_RE = re.compile(r"^\s*from badgeware import [^\n]*\n?", re.MULTILINE)
IMPORT_BADGEWARE_BARE_RE = re.compile(r"^\s*import badgeware\s*\n?", re.MULTILINE)

MAIN_GUARD_RE = re.compile(
    r'if __name__ == ["\']__main__["\']:\s*\n\s*run\(update\)\s*\n?'
)


def port_file(path: Path):
    text = path.read_text()
    original = text
    notes = []

    text = IMPORT_BADGEWARE_RE.sub("", text)
    text = IMPORT_BADGEWARE_BARE_RE.sub("", text)

    for pattern, repl in SIMPLE_RENAMES:
        text = re.sub(pattern, repl, text)

    text = BUTTON_STATE_RE.sub(lambda m: f"badge.{m.group(2)}({m.group(1)})", text)
    text = BARE_BUTTON_RE.sub(lambda m: m.group(1), text)
    text = DRAW_CALL_RE.sub("screen.shape(", text)

    if MAIN_GUARD_RE.search(text):
        text = MAIN_GUARD_RE.sub("run(update)\n", text)
    elif "run(update)" not in text and "def update(" in text:
        notes.append("no run(update) call found - check manually")

    # flags for things this script deliberately does not rewrite
    for needle, note in [
        ("SpriteSheet(", "SpriteSheet() constructor - needs manual conversion to image.load(path).spritesheet(cols, rows)"),
        (".animation(", ".animation()/.frame()/.count() - old badge25-only API, needs the Animation shim"),
        ("scale_blit(", "scale_blit() - needs manual conversion to blit(img, rect(x, y, w, h))"),
        ("network.WLAN", "raw network.WLAN usage - needs manual conversion to wifi.connect()"),
        ("urlopen(", "urlopen() - needs manual conversion to socket/fetch based request"),
        (".alpha = ", "per-image .alpha assignment - source alpha is ignored since v3.0.0, use screen.alpha instead"),
        ("io.held", "bare io.held/io.pressed/... call - check manually"),
        ("io.pressed", "bare io.pressed call - check manually"),
        ("io.released", "bare io.released call - check manually"),
        ("io.changed", "bare io.changed call - check manually"),
    ]:
        if needle in text:
            notes.append(note)

    if text != original:
        path.write_text(text)
    return notes


def main(root):
    root = Path(root)
    for py_file in sorted(root.rglob("*.py")):
        notes = port_file(py_file)
        if notes:
            print(f"\n{py_file}")
            for n in notes:
                print(f"  - {n}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
