import sys
import os

sys.path.insert(0, "/system/apps/wigle")
os.chdir("/system/apps/wigle")

import binascii
import gc
import json
import network
from net_compat import urlopen

# use the full 320x240 panel instead of the default 160x120 - the badge
# image from WiGLE is 200px wide and the stats need room to breathe
badge.mode(HIRES)
SCREEN_W = 320
SCREEN_H = 240

phosphor = color.rgb(211, 250, 55, 150)
white = color.rgb(235, 245, 255)
faded = color.rgb(235, 245, 255, 100)
green = color.rgb(46, 160, 67)
red = color.rgb(248, 81, 73)
small_font = font.ark
large_font = font.absolute

WIFI_TIMEOUT = 60
# WiGLE's own API returns a link to its own badge image for the account
# (its colour reflects that account's network count tier) - we fetch and
# display that image as-is rather than drawing our own version of it.
STATS_URL = "https://api.wigle.net/api/v2/stats/user?user={user}"

WIFI_PASSWORD = None
WIFI_SSID = None
WIGLE_API_NAME = None
WIGLE_API_TOKEN = None
WIGLE_USERNAME = None

wlan = None
connected = False
ticks_start = None


def message(text):
    print(text)


def format_count(n):
    if n is None:
        return "--"
    if n >= 1000000:
        return "{:.1f}M".format(n / 1000000)
    if n >= 1000:
        return "{:.1f}K".format(n / 1000)
    return str(n)


def get_connection_details():
    global WIFI_PASSWORD, WIFI_SSID, WIGLE_API_NAME, WIGLE_API_TOKEN, WIGLE_USERNAME

    if WIFI_SSID is not None and WIGLE_USERNAME is not None:
        return True

    try:
        sys.path.insert(0, "/")
        try:
            import secrets
        finally:
            try:
                sys.path.pop(0)
            except Exception:
                pass
        WIFI_PASSWORD = getattr(secrets, "WIFI_PASSWORD", None)
        WIFI_SSID = getattr(secrets, "WIFI_SSID", None)
        WIGLE_API_NAME = getattr(secrets, "WIGLE_API_NAME", None)
        WIGLE_API_TOKEN = getattr(secrets, "WIGLE_API_TOKEN", None)
        WIGLE_USERNAME = getattr(secrets, "WIGLE_USERNAME", None)
    except ImportError:
        pass
    except Exception:
        pass

    if not WIFI_SSID:
        return False
    if not (WIGLE_API_NAME and WIGLE_API_TOKEN and WIGLE_USERNAME):
        return False

    return True


def wlan_start():
    global wlan, ticks_start, connected

    if ticks_start is None:
        ticks_start = badge.ticks

    if connected:
        return True

    if wlan is None:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)

        if wlan.isconnected():
            connected = True
            return True

        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        print("Connecting to WiFi...")

    connected = wlan.isconnected()

    if badge.ticks - ticks_start < WIFI_TIMEOUT * 1000:
        if connected:
            print("WiFi connected!")
            return True
    elif not connected:
        return False

    return True


def auth_header():
    token = WIGLE_API_NAME + ":" + WIGLE_API_TOKEN
    encoded = binascii.b2a_base64(token.encode()).decode().strip()
    return {"Authorization": "Basic " + encoded, "User-Agent": "Badgeware-WiGLE-Stats"}


def async_fetch_to_disk(url, file, headers, force_update=False, timeout_ms=25000):
    if not force_update and file_exists(file):
        return

    start_ticks = badge.ticks
    try:
        response = urlopen(url, headers=headers)
        data = bytearray(512)
        total = 0
        with open(file, "wb") as f:
            while True:
                if timeout_ms is not None and (badge.ticks - start_ticks) > timeout_ms:
                    raise TimeoutError("Fetch timed out after {} ms".format(timeout_ms))
                length = response.readinto(data)
                if length == 0:
                    break
                total += length
                f.write(data[:length])
                yield
        del data
        del response
    except Exception as e:
        try:
            if file_exists(file):
                os.remove(file)
        except Exception:
            pass
        if isinstance(e, TimeoutError):
            raise
        raise RuntimeError("Fetch from {} to {} failed. {}".format(url, file, e)) from e


def get_stats(user, force_update=False):
    message("Getting WiGLE stats for {}...".format(user.handle))
    try:
        yield from async_fetch_to_disk(
            STATS_URL.format(user=user.handle), "/wigle_stats.json", auth_header(), force_update
        )
    except Exception as e:
        message("Failed to get WiGLE stats: {}".format(e))
        user.error = "Fetch Error"
        return

    try:
        r = json.loads(open("/wigle_stats.json", "r").read())
        if not r.get("success"):
            user.error = "Not Found"
            return
        stats = r.get("statistics") or {}
        # the *GPS variants are the geolocated counts WiGLE's own badge
        # image shows (discoveredWiFi/Bt/Cell without GPS are much larger
        # totals that include non-geolocated observations)
        user.wifi = stats.get("discoveredWiFiGPS", 0)
        user.bt = stats.get("discoveredBtGPS", 0)
        user.cell = stats.get("discoveredCellGPS", 0)
        user.rank = r.get("rank")
        user.prev_rank = stats.get("prevRank")
        user.month_rank = r.get("monthRank")
        user.prev_month_rank = stats.get("prevMonthRank")
        badge_url = r.get("imageBadgeUrl")
        if badge_url and badge_url.startswith("/"):
            badge_url = "https://api.wigle.net" + badge_url
        user.badge_url = badge_url
        del r
        gc.collect()
    except Exception as e:
        message("Failed to parse WiGLE stats: {}".format(e))
        user.error = "Parse Error"


def get_badge_image(user, force_update=False):
    if not user.badge_url:
        user.badge = False
        return
    message("Getting WiGLE badge image...")
    try:
        yield from async_fetch_to_disk(user.badge_url, "/wigle_badge.png", None, force_update)
        if file_exists("/wigle_badge.png"):
            user.badge = image.load("/wigle_badge.png")
        else:
            user.badge = False
    except Exception as e:
        message("Failed to get badge image: {}".format(e))
        user.badge = False


class User:
    def __init__(self):
        self.handle = None
        self.reset()

    def reset(self):
        self.wifi = None
        self.bt = None
        self.cell = None
        self.rank = None
        self.prev_rank = None
        self.month_rank = None
        self.prev_month_rank = None
        self.badge_url = None
        self.badge = None
        self.error = None
        self._task = None

    def stage(self):
        if self.error:
            return None
        if self.wifi is None:
            return "stats"
        if self.badge is None:
            return "badge"
        return None

    def fetch_next(self):
        stage = self.stage()
        if stage == "stats":
            self._task = self._task or get_stats(self)
        elif stage == "badge":
            self._task = self._task or get_badge_image(self)
        else:
            return
        try:
            next(self._task)
        except StopIteration:
            self._task = None
        except Exception:
            self._task = None
            self.error = "fetch error"

    def draw_stat(self, title, value, cx, y):
        # cx is the horizontal CENTER of this stat's column
        screen.font = large_font
        screen.pen = white if value is not None else faded
        text = format_count(value) if value is not None else "--"
        w, _ = screen.measure_text(text, 2)
        screen.text(text, cx - (w / 2), y, 2)

        screen.font = small_font
        screen.pen = phosphor
        w, _ = screen.measure_text(title, 2)
        screen.text(title, cx - (w / 2), y + 26, 2)

    def draw_rank(self, title, current, previous, cx, y):
        screen.font = large_font
        screen.pen = white if current is not None else faded
        text = "#{}".format(current) if current is not None else "--"
        w, _ = screen.measure_text(text, 2)
        screen.text(text, cx - (w / 2), y, 2)

        screen.font = small_font
        screen.pen = phosphor
        w, _ = screen.measure_text(title, 2)
        screen.text(title, cx - (w / 2), y + 26, 2)

        if current is not None and previous is not None and previous != current:
            delta = previous - current
            arrow = "^" if delta > 0 else "v"
            screen.pen = green if delta > 0 else red
            delta_text = "{} {}".format(arrow, abs(delta))
            w, _ = screen.measure_text(delta_text, 2)
            screen.text(delta_text, cx - (w / 2), y + 44, 2)

    def draw(self, connected):
        screen.font = large_font
        handle = self.handle
        stage = self.stage()

        if stage and connected:
            handle = "fetching stats..." if stage == "stats" else "fetching badge..."
            self.fetch_next()
        elif self.error:
            handle = self.error

        if not connected:
            handle = "connecting..."

        w, _ = screen.measure_text(handle, 2)
        screen.pen = white
        screen.text(handle, (SCREEN_W / 2) - (w / 2), 4, 2)

        # three stat columns spread evenly across the full panel width,
        # right under the title
        self.draw_stat("wifi", self.wifi, SCREEN_W / 6, 40)
        self.draw_stat("bt", self.bt, SCREEN_W / 2, 40)
        self.draw_stat("cell", self.cell, SCREEN_W * 5 / 6, 40)

        # two rank columns, also spread across the full width
        self.draw_rank("overall", self.rank, self.prev_rank, SCREEN_W / 4, 100)
        self.draw_rank("month", self.month_rank, self.prev_month_rank, SCREEN_W * 3 / 4, 100)

        if self.badge:
            # WiGLE's own badge image, pinned to the bottom of the panel
            w, h = self.badge.width, self.badge.height
            screen.blit(self.badge, rect((SCREEN_W / 2) - (w / 2), SCREEN_H - h - 15, w, h))


user = User()


def no_secrets_error():
    screen.font = large_font
    screen.pen = white
    msg = "Missing details!"
    w, _ = screen.measure_text(msg)
    screen.text(msg, (SCREEN_W / 2) - (w / 2), 5)

    screen.font = small_font
    screen.pen = phosphor
    screen.text(
        "Edit secrets.py, add:\nWIGLE_USERNAME = \"you\"\nWIGLE_API_NAME = \"...\"\nWIGLE_API_TOKEN = \"...\"\n(from wigle.net/account)",
        10, 30
    )


def connection_error():
    screen.font = large_font
    screen.pen = white
    msg = "Connection Failed!"
    w, _ = screen.measure_text(msg)
    screen.text(msg, (SCREEN_W / 2) - (w / 2), 5)
    screen.font = small_font
    screen.pen = phosphor
    screen.text("Could not connect\nto Wi-Fi.", 10, 30)


def update():
    screen.pen = color.rgb(13, 17, 23)
    screen.shape(shape.rectangle(0, 0, SCREEN_W, SCREEN_H))

    if badge.pressed(BUTTON_A) and badge.pressed(BUTTON_C):
        user.reset()

    if not get_connection_details():
        no_secrets_error()
        return

    user.handle = WIGLE_USERNAME

    if wlan_start():
        user.draw(connected)
    else:
        connection_error()


run(update)
