#!/usr/bin/env python3
"""Patch the badge's launcher menu so a cold boot goes straight into a
chosen app, while HOME still returns to the menu as normal.

Generalizes the same technique ccstats/tools/enable-autoboot.py uses for
itself, parameterized for any installed app.

How it works
------------
- A fresh power-on or RESET-button press is a PWRON reset (machine.reset_cause()
  == machine.PWRON_RESET). The patch checks for this and, if it matches,
  returns the target app's path from the menu's own update() instead of
  running the menu - main.py then launches straight into it.
- HOME pressed inside an app triggers a *watchdog* reset (a different
  reset_cause), which is NOT PWRON - so it always falls through to the
  normal menu. Nothing app-specific needed for this: it's how HOME works.
- The patch is idempotent: re-running it (even for a different app) finds
  and replaces its own previously-inserted block rather than stacking up
  duplicates.
- Applies directly to /system/apps/menu/__init__.py, which is normally
  read-only - it uses the same raw flash remount-and-write trick as
  ccstats' own installer. This modifies real firmware behaviour and will
  need re-applying after a Pimoroni firmware update resets the stock menu.

Usage:
    tools/enable_autoboot.py <app_folder_name> [path-to-mpremote]
    tools/enable_autoboot.py --disable [path-to-mpremote]

Example (boot straight into this repo's own "badge" app):
    tools/enable_autoboot.py badge
"""

import base64
import os
import subprocess
import sys
import tempfile

MENU_PATH = "/system/apps/menu/__init__.py"
BLOCK_BEGIN = "# --- autoboot patch"
BLOCK_END = "# --- end autoboot patch ---\n"
HOOK_LINE = "on_exit = run(update).result"

AUTO_BOOT_BLOCK = '''
# --- autoboot patch (inserted by tools/enable_autoboot.py) ---
# Cold boots (power-on / RESET button = PWRON cause) go straight into the
# app below; HOME inside an app reboots via the watchdog (a different
# reset_cause), which lands here and shows the menu instead - HOME always
# returns to the menu, no matter what app is running.
import machine as _autoboot_machine

_autoboot_target = "/system/apps/%(app)s"

_autoboot_pending = (
    file_exists(_autoboot_target + "/__init__.py")
    and _autoboot_machine.reset_cause() == _autoboot_machine.PWRON_RESET
)

_autoboot_menu_update = update


def update():
    global _autoboot_pending
    if _autoboot_pending:
        _autoboot_pending = False
        return _autoboot_target
    return _autoboot_menu_update()
# --- end autoboot patch ---

'''

INSTALLER_TEMPLATE = '''\
import binascii
import os
import rp2
import vfs

os.umount("/system")
user_flash_size = rp2.Flash().ioctl(4, 0) * rp2.Flash().ioctl(5, 0)
fat_block_device = rp2.Flash(start=0, len=user_flash_size - 1024 * 1024)
vfs.mount(vfs.VfsFat(fat_block_device), "/system")

content = binascii.a2b_base64(%r)
with open(%r, "wb") as file:
    file.write(content)
print("menu patched,", len(content), "bytes")
'''


def fetch_menu_source(mpremote_binary):
    menu_source = subprocess.run(
        [mpremote_binary, "cat", MENU_PATH], capture_output=True, check=True
    ).stdout.decode()
    # normalize line endings so the block markers / HOOK_LINE match
    # regardless of the stock file's terminator style
    return menu_source.replace("\r\n", "\n").replace("\r", "\n")


def strip_existing_patch(menu_source):
    if BLOCK_BEGIN not in menu_source:
        return menu_source, False
    begin = menu_source.find(BLOCK_BEGIN)
    end = menu_source.find(BLOCK_END)
    if begin == -1 or end == -1:
        sys.exit(
            "found the patch marker but not the block bounds - inspect %s by hand"
            % MENU_PATH
        )
    return menu_source[:begin] + menu_source[end + len(BLOCK_END):], True


def write_menu_source(mpremote_binary, patched_source):
    encoded = base64.b64encode(patched_source.encode()).decode()
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as installer:
        installer.write(INSTALLER_TEMPLATE % (encoded, MENU_PATH))
        installer_path = installer.name
    try:
        subprocess.run([mpremote_binary, "run", installer_path], check=True)
        subprocess.run([mpremote_binary, "reset"], check=True)
    finally:
        os.unlink(installer_path)


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)

    disable = args[0] == "--disable"
    app_name = None if disable else args[0]
    mpremote_binary = args[1] if len(args) > 1 else "mpremote"

    menu_source = fetch_menu_source(mpremote_binary)
    menu_source, had_patch = strip_existing_patch(menu_source)

    if disable:
        if not had_patch:
            print("no autoboot patch was installed - nothing to do")
            return
        write_menu_source(mpremote_binary, menu_source)
        print("autoboot disabled - cold boots go to the menu again")
        return

    if HOOK_LINE not in menu_source:
        sys.exit(
            "could not find %r in the installed menu - the menu changed "
            "upstream; update this tool before patching" % HOOK_LINE
        )

    block = AUTO_BOOT_BLOCK % {"app": app_name}
    patched_source = menu_source.replace(HOOK_LINE, block + HOOK_LINE)
    write_menu_source(mpremote_binary, patched_source)
    if had_patch:
        print("replaced existing autoboot patch - now targeting", app_name)
    else:
        print("autoboot patch installed - now targeting", app_name)
    print("power-cycle (or RESET) now boots into", app_name, "- HOME returns to the menu")


if __name__ == "__main__":
    main()
