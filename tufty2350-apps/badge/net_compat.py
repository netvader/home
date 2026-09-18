"""
Resilient urlopen() wrapper.

The GitHub Universe 2025 (badge25) firmware's `urllib.urequest.urlopen()`
accepted a `headers=` keyword. That isn't documented anywhere in the
current Pimoroni tufty2350 (v3.1.0+) Badgeware API docs - if this
firmware's MicroPython build doesn't support it, calling with `headers=`
raises a TypeError. This falls back to a plain request (dropping the
custom headers, usually just a User-Agent) rather than crashing the app.

Copied verbatim into each app that needs it - not a shared library,
since each app folder is self-contained on the badge's filesystem.
"""
from urllib.urequest import urlopen as _urlopen


def urlopen(url, headers=None, data=None):
    kwargs = {}
    if headers is not None:
        kwargs["headers"] = headers
    if data is not None:
        kwargs["data"] = data
    try:
        return _urlopen(url, **kwargs)
    except TypeError:
        print("urlopen: headers/data kwargs unsupported on this firmware, retrying plain")
        return _urlopen(url)
