# Tufty2350 port of the GitHub Universe 2025 badge apps

This folder ports the apps from [`badge25/apps`](../badge25/apps) (written
against the GitHub Universe 2025 conference badge's own `badgeware.io`
Python API) onto the current **official Pimoroni [`tufty2350`](https://github.com/pimoroni/tufty2350)
firmware, v3.1.0**. That firmware's Badgeware API has gone through several
breaking revisions since (`v2.0.0`, `v3.0.0`) - this port targets the API
as documented at [pimoroni/badgeware-docs](https://github.com/pimoroni/badgeware-docs)
on 2026-09-18.

**This has not been tested on real hardware.** It's a careful, static port
based on the documented API and a from-scratch check of every file for
leftover old-API calls - see "How this was verified" below. Please try it
and report back anything that misbehaves.

## What's excluded, and why

| App | Reason |
|---|---|
| `quest` | Needs the GitHub Universe badge's IR receiver hardware (`aye_arr.nec.NECReceiver`) and conference-specific IR beacons. A retail Tufty2350 has no IR receiver. |
| `menu` | The badge25 app launcher (auto-discovers `/system/apps/*`, its own icon grid). The current `tufty2350` firmware ships its own menu - installing this one would just duplicate/conflict with it. |
| `startup` | The badge25 boot-splash animation. Same reasoning as `menu` - the firmware already has its own. |

You asked to exclude apps needing the STEM kit (QwST Pad gamepad,
Multi-Sensor Stick) specifically - none of the remaining `badge25` apps
actually import `qwstpad` or any `breakout_*` sensor module, so nothing
else needed to be dropped on that basis.

## What changed, mechanically

The old badge25 firmware required `from badgeware import screen, color, ...`
and exposed a slightly different surface. The current firmware makes
`screen`, `badge`, `color`, `font`, `image`, `shape`, `mat3`, `vec2`, `rect`,
`run`, `State`, the `BUTTON_*` constants, etc. **ambient globals** - no
import needed, available only inside an app launched from the menu.

| Old (badge25) | New (tufty2350 v3.1.0) |
|---|---|
| `from badgeware import screen, color, ...` | removed - nothing to import |
| `io.ticks` / `io.ticks_delta` | `badge.ticks` / `badge.ticks_delta` |
| `io.BUTTON_X in io.pressed` (also `held`/`released`/`changed`) | `badge.pressed(BUTTON_X)` (etc.) |
| `brushes.color(r,g,b,a)` | `color.rgb(r,g,b,a)` |
| `screen.brush = X` | `screen.pen = X` |
| `shapes.rectangle(...)` etc. | `shape.rectangle(...)` etc. |
| `screen.draw(x)` | `screen.shape(x)` |
| `Matrix()` | `mat3()` |
| `Image.load(...)` / `Image(w, h)` | `image.load(...)` / `image(w, h)` |
| `PixelFont.load(path)` | `font.load(path)` |
| `SpriteSheet(path, cols, rows)` | `image.load(path).spritesheet(cols, rows)` |
| `.animation(col, row, count)` / `.frame(n)` / `.count()` | not in the current API - see `badgeware_compat.py` below |
| `screen.scale_blit(img, x, y, w, h)` | `screen.blit(img, rect(x, y, w, h))` |
| `image.alpha = v` on a *source* sprite before blitting | ignored since v3.0.0 - set `screen.alpha = v` (the *destination*) instead |
| `if __name__ == "__main__": run(update)` | just `run(update)` unconditionally, as the last line |
| apps with a bare `def update():` and no `run()` call at all (`files`, `gitris`, `jezzball` relied on badge25's `main.py` calling `update()` for them) | `run(update)` added explicitly - the current firmware expects every app to own its main loop |
| `run(update, init=init, on_exit=on_exit)` (`monapet`, `wled`) | current `run()` only takes an update function, no init/on_exit hooks. `init()` is now called once before `run(update)`; the `on_exit` save is replaced with saving immediately at each point the relevant state changes (`monapet`) or a periodic 5s save inside `update()` (`wled`) |
| `brushes.xor(r, g, b)` (`sketch`'s cursor) | no XOR-blend brush exists in the current API - replaced with a plain pulsing `color.rgb(i, i, i)`. Visually similar, but the cursor is no longer guaranteed visible against every background colour. |

### `badgeware_compat.py`

Three apps (`flappy`, `monapet`, `sketch`) used badge25's `SpriteSheet`
class for animation playback (`.animation()`/`.frame()`/`.count()`), which
has no equivalent in the current `spritesheet` type (it only has
`.sprite(x, y)`/`.sprite(n)`). Each of those app folders has its own copy
of `badgeware_compat.py`, a small shim rebuilding that surface on top of
`image.load(path).spritesheet(cols, rows)`. It's copied per-app (not a
shared library) because each app folder is self-contained on the badge's
filesystem.

### `net_compat.py`

`badge`, `crypto`, `stocks`, `weather`, and `wled` fetch data over HTTP
using `from urllib.urequest import urlopen(url, headers=...)`. That
`headers=` keyword is not documented anywhere in the current Badgeware
API docs - it was specific to the GitHub Universe badge's own firmware
build. **This is the most likely single point of failure if a previous
port didn't work for you.** Each of these apps has its own copy of
`net_compat.py`, a thin wrapper that tries `urlopen(url, headers=...)`
and transparently falls back to a plain `urlopen(url)` (dropping the
custom header, usually just a `User-Agent`) if the firmware's build
raises `TypeError` on the keyword. Everything else about the networking
code (raw `network.WLAN`, manual connect/timeout handling) is left as-is,
since it's standard MicroPython functionality that `badgewa.re`'s own
docs point to as a supported alternative to the `wifi` module.

If `net_compat.py`'s fallback still doesn't help (i.e. `urlopen` itself
doesn't exist, or `network.WLAN` behaves differently on your firmware
build), the fix is to switch these apps to the officially documented
`wifi.connect()` + `fetch.url()`/`fetch.json()` pattern from
[the networking guide](https://github.com/pimoroni/badgeware-docs/blob/main/guides/networking.md) -
`fetch` doesn't support custom headers though, so a `GITHUB_TOKEN` for
higher API rate limits would have to be dropped.

## How this was verified

No real hardware was available to test against, so verification was
static:

1. Every mechanical rename above was applied with a script and then
   double-checked with repeated greps across the whole tree for leftover
   `io.`, `brushes.`, `shapes.`, `Matrix`, `PixelFont`, `SpriteSheet(`
   (outside the compat shim), `screen.draw(`, `scale_blit(`, and
   `from badgeware import` - all clean.
2. Every `.py` file parses as valid Python (`ast.parse`).
3. A best-effort static-analysis pass checked every name used-but-not
   assigned/imported in each file against the documented ambient globals
   - nothing unresolved turned up beyond expected `except ... as e` false
   positives.

This does **not** catch runtime-only issues (wrong argument order,
firmware quirks, timing bugs, or anything data-dependent). Please treat
this as a solid first draft, flash it, and report back what breaks.

## Installing

1. Flash the latest `-with-filesystem` firmware from
   [pimoroni/tufty2350/releases](https://github.com/pimoroni/tufty2350/releases/latest).
2. Double-tap `RESET` to enter disk mode; a `Tufty2350` drive appears.
3. Run `./install.sh` (see below) to copy the apps and `secrets.py` onto it.
4. Fill in `secrets.py` on the drive with your Wi-Fi details and, for
   `badge`, your GitHub username.
5. Eject and reset.

### `install.sh`

```sh
./install.sh                              # install everything to /Volumes/TUFTY
./install.sh /Volumes/TUFTY badge flappy  # install just two apps
./install.sh /Volumes/BADGER              # different volume name/mount point
```

On macOS, copying files onto a non-HFS+ volume (the badge's FAT32/exFAT
filesystem) with Finder or plain `cp` scatters `._xxx` "AppleDouble"
sidecar files everywhere. The on-device menu doesn't expect these when it
scans `/system/apps/` for icons, and can crash with `cannot load PNG:
corrupt or truncated data` while trying to read one. `install.sh` sets
`COPYFILE_DISABLE=1` before copying (which stops macOS writing them in
the first place) and sweeps up any that appear anyway. If you'd rather
copy manually, just `export COPYFILE_DISABLE=1` in your shell first - and
if a badge already has `._*` files on it from an earlier copy, delete
them (`find /Volumes/TUFTY -name '._*' -delete`) before rebooting it.
