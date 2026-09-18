"""
Small compatibility shim bridging the old GitHub Universe 2025 (badge25)
SpriteSheet/animation API onto the current Pimoroni tufty2350 (v3.1.0+)
Badgeware `image`/`spritesheet` API.

The old badge25 firmware's `SpriteSheet(path, cols, rows)` returned an
object with `.animation(col, row, count)` / `.frame(n)` / `.count()` for
sprite-sheet animation playback. The current firmware's `spritesheet`
type (see /api/spritesheet.md) only exposes `.sprite(x, y)` - this file
rebuilds the old surface on top of that.

Copied verbatim into each app that needs it - not a shared library,
since each app folder is self-contained on the badge's filesystem.
"""


def SpriteSheet(path, cols, rows):
    return image.load(path).spritesheet(cols, rows)


class Animation:
    def __init__(self, sheet, col=0, row=0, count=None):
        self.sheet = sheet
        self.col = col
        self.row = row
        self.count_ = count if count is not None else sheet.cols - col

    def frame(self, i):
        i = int(i) % self.count_
        return self.sheet.sprite(self.col + i, self.row)

    def count(self):
        return self.count_


def scale_blit(dest, source, x, y, w, h):
    dest.blit(source, rect(x, y, w, h))
