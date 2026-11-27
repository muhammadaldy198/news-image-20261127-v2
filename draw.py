"""news-image-20261127 v2 — broadsheet renderer (Kirana, Hunter Office).

Renders stories.json into a 1024x1024 front page: FRIDAY IN THREE ACTS.
Architecture: JSON -> PIL + slot + verify script. Deterministic: no clock,
no network, seeded randomness only. Re-render with system python3 only.
"""
import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

W = 1024
H = 1024
MARGIN = 12
GUTTER = 8
CONTENT_W = W - 2 * MARGIN
COL_W = (CONTENT_W - 2 * GUTTER) // 3

PAPER = (247, 243, 234)
INK = (20, 20, 20)
MUTED = (96, 90, 78)
RED = (179, 38, 30)
NAVY = (26, 36, 51)
NAVY2 = (36, 62, 92)
DUSK_TOP = (28, 44, 68)
DUSK_BOT = (48, 74, 104)
RULE = (198, 190, 172)
FAINT = (216, 210, 196)
GREEN = (31, 61, 43)
GOLD = (201, 162, 39)
LINE2 = (64, 58, 48)

BUDGET = [
    ("masthead", 52),
    ("lead", 48),
    ("numbers", 18),
    ("regions", 14),
    ("act1_head", 16),
    ("nz_hero", 150),
    ("act1_briefs", 110),
    ("act2_head", 16),
    ("ukraine_hero", 156),
    ("act2_briefs", 66),
    ("act3_head", 16),
    ("nfl_banner", 150),
    ("act3_briefs", 110),
    ("saturday", 30),
    ("datecheck", 60),
    ("footer", 12),
]
assert sum(h for _, h in BUDGET) == 1024, "budget must sum to 1024"
Y = {}
_y = 0
for _name, _h in BUDGET:
    Y[_name] = _y
    _y += _h

FONT_DIR = "/usr/share/fonts/truetype/noto"


def load_font(name, size):
    path = os.path.join(FONT_DIR, name)
    assert os.path.exists(path), "missing font: %s" % path
    return ImageFont.truetype(path, size)


F_TITLE = load_font("NotoSerifDisplay-Black.ttf", 36)
F_DATE = load_font("NotoSans-Bold.ttf", 11)
F_EAR = load_font("NotoSans-Bold.ttf", 10)
F_KICKER = load_font("NotoSans-Bold.ttf", 10)
F_LEAD = load_font("NotoSerifDisplay-Black.ttf", 27)
F_DECK = load_font("NotoSerif-Regular.ttf", 12)
F_NUM = load_font("NotoSansMono-Bold.ttf", 11)
F_REG = load_font("NotoSans-Regular.ttf", 10)
F_ACT = load_font("NotoSerifDisplay-Black.ttf", 13)
F_ACTSUB = load_font("NotoSans-Bold.ttf", 10)
F_BRIEF = load_font("NotoSerif-Bold.ttf", 12)
F_BTAG = load_font("NotoSans-Bold.ttf", 11)
F_HERO_H = load_font("NotoSerifDisplay-Black.ttf", 32)
F_HERO_H2 = load_font("NotoSerifDisplay-Black.ttf", 26)
F_HERO_D = load_font("NotoSans-Regular.ttf", 12)
F_SAT_H = load_font("NotoSans-Bold.ttf", 10)
F_SAT = load_font("NotoSans-Regular.ttf", 10)
F_MAP_L = load_font("NotoSans-Bold.ttf", 8)
F_DC_H = load_font("NotoSans-Bold.ttf", 10)
F_DC = load_font("NotoSansMono-Regular.ttf", 9)
F_FOOT = load_font("NotoSans-Regular.ttf", 9)
F_DECK2 = load_font("NotoSans-Regular.ttf", 8)
F_LABEL = load_font("NotoSans-Bold.ttf", 10)
F_LEGEND = load_font("NotoSans-Regular.ttf", 8)

BOXES = []


def record(label, x0, y0, x1, y1):
    BOXES.append((label, x0, y0, x1, y1))


def text_w(font, s):
    """Advance width (pen movement), not ink edge — use for layout."""
    return int(round(font.getlength(s)))


def text_h(font, s):
    b = font.getbbox(s)
    return b[3] - b[1]


def ink_box(font, s, x, y):
    """True ink extents of text drawn at (x, y): bbox offsets matter."""
    b = font.getbbox(s)
    return (x + b[0], y + b[1], x + b[2], y + b[3])


def draw_left(d, x, y, s, font, fill):
    d.text((x, y), s, font=font, fill=fill)
    record(s[:24], *ink_box(font, s, x, y))


def draw_center(d, cx, y, s, font, fill):
    w = text_w(font, s)
    x = cx - w // 2
    d.text((x, y), s, font=font, fill=fill)
    record(s[:24], *ink_box(font, s, x, y))


def fit_font(names, size, s, max_w):
    """Return a font (shrinking size) that fits s in max_w, else raise."""
    while size >= 8:
        f = load_font(names, size)
        if text_w(f, s) <= max_w:
            return f
        size -= 1
    raise AssertionError("cannot fit text in %dpx: %s" % (max_w, s))


def wrap_lines(font, s, max_w, max_lines):
    words = s.split()
    lines = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_w(font, trial) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    assert len(lines) <= max_lines, "wrap overflow (%d>%d): %s" % (
        len(lines), max_lines, s)
    return lines


def vgrad(img, box, top, bot):
    x0, y0, x1, y1 = box
    h = max(1, y1 - y0)
    for i in range(h):
        t = i / h
        c = tuple(int(top[k] + (bot[k] - top[k]) * t) for k in range(3))
        img_draw = ImageDraw.Draw(img)
        img_draw.line([(x0, y0 + i), (x1, y0 + i)], fill=c + (255,))


def glow(ov, cx, cy, r, color):
    """Soft radial glow on an RGBA overlay: concentric circles, fading alpha."""
    d = ImageDraw.Draw(ov)
    steps = 12
    for i in range(steps, 0, -1):
        rr = r * i // steps
        a = int(150 * (1 - i / steps) ** 2) + 12
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                  fill=color + (a,))


# ---------------------------------------------------------------- heroes

def paint_ukraine(img, box):
    """Night sky over a dark city: drone swarm, three blasts, lit windows."""
    x0, y0, x1, y1 = box
    vgrad(img, box, DUSK_TOP, DUSK_BOT)
    d = ImageDraw.Draw(img, "RGBA")
    rng = random.Random(27)
    for _ in range(70):
        sx = rng.randint(x0 + 4, x1 - 4)
        sy = rng.randint(y0 + 4, y0 + (y1 - y0) // 2)
        r = rng.choice([1, 1, 1, 2])
        d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(220, 225, 235, 200))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow(ov, x0 + 180, y0 + 118, 64, (255, 150, 40))
    glow(ov, x0 + 640, y0 + 96, 52, (255, 180, 60))
    glow(ov, x0 + 880, y0 + 132, 40, (255, 120, 30))
    img.alpha_composite(ov)
    d = ImageDraw.Draw(img, "RGBA")
    base = y1 - 44
    bx = x0
    while bx < x1:
        bw = rng.randint(34, 72)
        bh = rng.randint(26, 66)
        d.rectangle([bx, base - bh, bx + bw, base + 30], fill=(10, 16, 28, 255))
        for wy in range(base - bh + 6, base - 2, 10):
            for wx in range(bx + 5, bx + bw - 4, 11):
                if rng.random() < 0.4:
                    d.rectangle([wx, wy, wx + 3, wy + 4],
                                fill=(255, 205, 110, 220))
        bx += bw + 4
    d.rectangle([x0, base, x1, y1], fill=(8, 12, 22, 255))
    for _ in range(16):
        dx = rng.randint(x0 + 10, x1 - 10)
        dy = rng.randint(y0 + 14, y0 + 84)
        d.line([(dx, dy), (dx + rng.randint(10, 26), dy + rng.randint(2, 8))],
               fill=(200, 205, 215, 160), width=1)
        d.ellipse([dx - 2, dy - 2, dx + 2, dy + 2], fill=(20, 20, 20, 255))
        d.ellipse([dx - 1, dy - 1, dx + 1, dy + 1], fill=(255, 60, 40, 255))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    rng2 = random.Random(155)
    for cx, cy, rr in [(x0 + 180, y0 + 118, 26), (x0 + 640, y0 + 96, 20),
                       (x0 + 880, y0 + 132, 15)]:
        od.ellipse([cx - 12, cy - rr - 34, cx + 12, cy - rr + 6],
                   fill=(70, 70, 80, 90))
        od.ellipse([cx - 2, cy - rr - 48, cx + 18, cy - rr - 12],
                   fill=(70, 70, 80, 70))
        pts = []
        spikes = 12
        for k in range(spikes * 2):
            ang = math.pi * k / spikes
            rad = rr * (1.0 if k % 2 == 0 else 0.42)
            rad *= 1 + rng2.uniform(-0.12, 0.12)
            pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
        od.polygon(pts, fill=(255, 190, 80, 235))
        core = [(cx + rr * 0.45 * math.cos(math.pi * k / 6),
                 cy + rr * 0.45 * math.sin(math.pi * k / 6)) for k in range(12)]
        od.polygon(core, fill=(255, 244, 205, 255))
    img.alpha_composite(ov)


def paint_nz(img, box):
    """Wellington at dusk: Parliament House at left, the Beehive in
    silhouette at right, one red window — the missing seat."""
    x0, y0, x1, y1 = box
    vgrad(img, box, (238, 226, 198), (214, 196, 168))
    cx = (x0 + x1) // 2
    band_top = y1 - 48
    sx, sy = cx - 60, band_top - 70
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow(ov, sx, sy, 46, (255, 214, 140))
    img.alpha_composite(ov)
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse([sx - 16, sy - 16, sx + 16, sy + 16], fill=(255, 226, 150, 255))
    hx0, hx1 = x0 + 90, x0 + 330
    d.polygon([(hx0, band_top - 52), ((hx0 + hx1) // 2, band_top - 72),
               (hx1, band_top - 52)], fill=(40, 54, 78, 255))
    d.rectangle([hx0, band_top - 52, hx1, band_top], fill=(30, 44, 66, 255))
    for i in range(8):
        colx = hx0 + 18 + i * 28
        d.line([(colx, band_top - 48), (colx, band_top - 4)],
               fill=(232, 220, 195, 255), width=3)
    bx = cx + 160
    floors = [(120, 14), (112, 13), (104, 13), (96, 12), (88, 12), (78, 12),
              (66, 11)]
    fy = band_top
    red_done = False
    for w, h in floors:
        fy -= h
        d.rectangle([bx - w // 2, fy, bx + w // 2, fy + h],
                    fill=(26, 42, 68, 255))
        nw = max(2, w // 16)
        for i in range(nw):
            wx = bx - w // 2 + 8 + i * 15
            wy = fy + h // 2 - 2
            if not red_done and w == 96 and i == 3:
                d.rectangle([wx, wy, wx + 4, wy + 4], fill=RED + (255,))
                red_done = True
            else:
                d.rectangle([wx, wy, wx + 4, wy + 4], fill=(255, 214, 130, 255))
    d.ellipse([bx - 20, fy - 10, bx + 20, fy + 2], fill=(26, 42, 68, 255))
    d.line([(bx, fy - 10), (bx, fy - 20)], fill=(26, 42, 68, 255), width=2)
    d.line([(x0, band_top), (x1, band_top)], fill=(120, 105, 80, 255), width=2)


def paint_nfl(img, box):
    """Night stadium: three score panels, light towers, yard lines."""
    x0, y0, x1, y1 = box
    vgrad(img, box, (30, 46, 72), (48, 74, 104))
    d = ImageDraw.Draw(img, "RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for tx in (x0 + 70, x1 - 70):
        od.line([(tx, y0 + 8), (tx, y0 + 52)], fill=(220, 225, 235, 200),
                width=3)
        for lx in (-16, 0, 16):
            od.ellipse([tx + lx - 4, y0 + 4, tx + lx + 4, y0 + 12],
                       fill=(255, 250, 220, 255))
        od.polygon([(tx - 18, y0 + 12), (tx + 18, y0 + 12),
                    (tx + 60, y0 + 60), (tx - 60, y0 + 60)],
                   fill=(255, 250, 220, 14))
    img.alpha_composite(ov)
    d = ImageDraw.Draw(img, "RGBA")
    panels = [("BEARS", "39–35"), ("EAGLES", "39–38"), ("BILLS", "13–10")]
    pw, ph = 220, 74
    gap = (CONTENT_W - 3 * pw) // 2
    py = y0 + 18
    for i, (team, score) in enumerate(panels):
        px = x0 + i * (pw + gap)
        d.rounded_rectangle([px, py, px + pw, py + ph], radius=8,
                            fill=(245, 241, 230, 255))
        d.rounded_rectangle([px, py, px + pw, py + ph], radius=8,
                            outline=GOLD + (255,), width=2)
        f_team = load_font("NotoSans-Bold.ttf", 13)
        f_score = load_font("NotoSerifDisplay-Black.ttf", 30)
        tw = text_w(f_team, team)
        d.text((px + (pw - tw) // 2, py + 6), team, font=f_team, fill=RED)
        sw = text_w(f_score, score)
        d.text((px + (pw - sw) // 2, py + 26), score, font=f_score, fill=INK)
    fy = y1 - 72
    d.rectangle([x0, fy, x1, y1 - 48], fill=(24, 64, 38, 255))
    for i in range(11):
        lx = x0 + i * (CONTENT_W // 10)
        d.line([(lx, fy), (lx, y1 - 48)], fill=(235, 240, 235, 180), width=1)
    rng = random.Random(39)
    for _ in range(46):
        cx = rng.randint(x0 + 4, x1 - 4)
        cy = rng.randint(y0 + 4, fy - 4)
        c = rng.choice([(255, 210, 90), (255, 255, 255), (200, 220, 255)])
        d.ellipse([cx - 1, cy - 1, cx + 1, cy + 1], fill=c + (210,))


# ---------------------------------------------------------------- layout

def hero_band(img, box, headline, deck, src="", ver=""):
    x0, y0, x1, y1 = box
    band_h = 48
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([x0, y1 - band_h, x1, y1], fill=(16, 26, 44, 235))
    f_h = fit_font("NotoSerifDisplay-Black.ttf", 26, headline, CONTENT_W - 24)
    draw_left(d, x0 + 12, y1 - band_h + 4, headline, f_h, (255, 255, 255))
    label = (src + " · " + ver).strip(" · ") if src else ""
    lw = text_w(F_LABEL, label) if label else 0
    f_d = fit_font("NotoSans-Regular.ttf", 12, deck, CONTENT_W - 24 - lw - 16)
    draw_left(d, x0 + 12, y1 - 14, deck, f_d, (215, 220, 230))
    if label:
        lx = x1 - 12 - lw
        assert x0 + 12 + text_w(f_d, deck) + 12 <= lx, \
            "hero deck collides with label"
        d.text((lx, y1 - 14), label, font=F_LABEL, fill=(255, 214, 130))
        record(label[:24], *ink_box(F_LABEL, label, lx, y1 - 14))


def draw_masthead(img, data):
    y0 = Y["masthead"]
    d = ImageDraw.Draw(img, "RGBA")
    m = data["masthead"]
    for side, txt in (("left", m["left_ear"]), ("right", m["right_ear"])):
        w = text_w(F_EAR, txt) + 16
        bx = MARGIN if side == "left" else W - MARGIN - w
        by = y0 + 16
        d.rectangle([bx, by, bx + w, by + 18], outline=INK, width=1)
        draw_left(d, bx + 8, by + 3, txt, F_EAR, INK)
    draw_center(d, W // 2, y0 + 1, m["name"], F_TITLE, INK)
    d.line([(MARGIN, y0 + 40), (W - MARGIN, y0 + 40)], fill=INK, width=1)
    draw_center(d, W // 2, y0 + 42, m["date"], F_DATE, INK)


def draw_lead(img, data):
    y0 = Y["lead"]
    d = ImageDraw.Draw(img, "RGBA")
    lead = data["lead"]
    draw_left(d, MARGIN, y0 + 1, lead["kicker"], F_KICKER, RED)
    f_h = fit_font("NotoSerifDisplay-Black.ttf", 24, lead["headline"],
                   CONTENT_W)
    draw_left(d, MARGIN, y0 + 11, lead["headline"], f_h, INK)
    draw_left(d, MARGIN, y0 + 37, lead["deck"], F_DECK, MUTED)
    label = (lead.get("src", "") + " · " + lead.get("ver", "")).strip(" · ")
    if label:
        lw = text_w(F_LABEL, label)
        lx = W - MARGIN - lw
        assert MARGIN + text_w(F_DECK, lead["deck"]) + 12 <= lx, \
            "lead deck collides with label"
        d.text((lx, y0 + 37), label, font=F_LABEL, fill=RED)
        record(label[:24], *ink_box(F_LABEL, label, lx, y0 + 37))


def draw_numbers(img, items):
    y0 = Y["numbers"]
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([MARGIN, y0 + 2, W - MARGIN, y0 + 17], fill=NAVY)
    s = " · ".join(items)
    f = fit_font("NotoSansMono-Bold.ttf", 11, s, CONTENT_W - 16)
    draw_center(d, W // 2, y0 + 3, s, f, (255, 255, 255))


def draw_regions(img, s):
    y0 = Y["regions"]
    d = ImageDraw.Draw(img, "RGBA")
    f = fit_font("NotoSans-Regular.ttf", 10, s, CONTENT_W)
    draw_center(d, W // 2, y0 + 1, s, f, (60, 55, 45))


def draw_act_header(img, y0, title, sub):
    d = ImageDraw.Draw(img, "RGBA")
    draw_left(d, MARGIN, y0 + 0, title, F_ACT, INK)
    sw = text_w(F_ACTSUB, sub)
    draw_left(d, W - MARGIN - sw, y0 + 1, sub, F_ACTSUB, RED)
    d.line([(MARGIN, y0 + 14), (W - MARGIN, y0 + 14)], fill=RULE, width=1)


def draw_briefs(img, y0, briefs):
    # Two-line briefs, 22px rows: line 1 = TAG + headline (11px bold),
    # line 2 = SOURCE + verification label + 1-line deck (8px).
    # No separator rules: the bold headline of the next row separates rows.
    d = ImageDraw.Draw(img, "RGBA")
    n = len(briefs)
    rows = (n + 2) // 3
    f_h = load_font("NotoSerif-Bold.ttf", 11)
    for i, b in enumerate(briefs):
        col = i // rows
        row = i % rows
        x = MARGIN + col * (COL_W + GUTTER)
        y = y0 + row * 22
        tag = b["tag"] + " — "
        head = b["headline"]
        tw = text_w(F_BTAG, tag) + 2 + text_w(f_h, head)
        assert tw <= COL_W, "brief too long (%d>%d): %s" % (tw, COL_W, head)
        draw_left(d, x, y + 0, tag, F_BTAG, RED)
        tx = x + text_w(F_BTAG, tag) + 2
        draw_left(d, tx, y + 0, head, f_h, INK)
        line2 = "%s · %s — %s" % (b["src"], b["ver"], b["deck"])
        w2 = text_w(F_DECK2, line2)
        assert w2 <= COL_W, "deck too long (%d>%d): %s" % (w2, COL_W, line2)
        draw_left(d, x, y + 14, line2, F_DECK2, LINE2)


def draw_saturday(img, data):
    y0 = Y["saturday"]
    d = ImageDraw.Draw(img, "RGBA")
    sat = data["saturday"]
    draw_left(d, MARGIN, y0 + 2, sat["header"], F_SAT_H, RED)
    s = " · ".join(sat["items"])
    f = fit_font("NotoSans-Regular.ttf", 10, s, CONTENT_W)
    draw_left(d, MARGIN, y0 + 15, s, f, INK)


def draw_datecheck(img, data):
    y0 = Y["datecheck"]
    d = ImageDraw.Draw(img, "RGBA")
    dc = data["datecheck"]
    assert len(dc["items"]) == 18, "datecheck must hold 18 items"
    d.rectangle([MARGIN, y0 + 2, W - MARGIN, y0 + 58], outline=RED, width=1)
    draw_left(d, MARGIN + 8, y0 + 5, dc["header"], F_DC_H, RED)
    legend = ("HOW SURE: OFFICIAL=confirmed · REPORTED=named source · "
              "CLAIM=unverified · ONGOING=developing")
    lw = text_w(F_LEGEND, legend)
    lx = W - MARGIN - 8 - lw
    assert MARGIN + 8 + text_w(F_DC_H, dc["header"]) + 12 <= lx, \
        "legend collides with datecheck header"
    d.text((lx, y0 + 5), legend, font=F_LEGEND, fill=MUTED)
    record(legend[:24], *ink_box(F_LEGEND, legend, lx, y0 + 5))
    for li in range(3):
        s = " · ".join(dc["items"][li * 6:(li + 1) * 6])
        f = fit_font("NotoSansMono-Regular.ttf", 10, s, CONTENT_W - 16)
        draw_left(d, MARGIN + 8, y0 + 19 + li * 14, s, f, MUTED)


def draw_footer(img, data):
    y0 = Y["footer"]
    d = ImageDraw.Draw(img, "RGBA")
    f = data["footer"]
    draw_left(d, MARGIN, y0 + 1, f["sources"], F_FOOT, MUTED)
    nw = text_w(F_FOOT, f["note"])
    nx = W - MARGIN - nw
    assert MARGIN + text_w(F_FOOT, f["sources"]) + 8 <= nx, \
        "footer sources collide with note"
    draw_left(d, nx, y0 + 1, f["note"], F_FOOT, MUTED)


def check_overlaps():
    bad = []
    for i in range(len(BOXES)):
        for j in range(i + 1, len(BOXES)):
            a = BOXES[i]
            b = BOXES[j]
            ox = min(a[3], b[3]) - max(a[1], b[1])
            oy = min(a[4], b[4]) - max(a[2], b[2])
            if ox > 0 and oy > 0:
                bad.append((a[0], b[0], ox, oy))
    assert not bad, "text overlap: %s" % (bad[:5],)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "entry.png")
    with open(os.path.join(here, "stories.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    ids = [data["lead"]["id"]]
    for act in data["acts"]:
        if "hero" in act:
            ids.append(act["hero"]["id"])
        ids.extend(b["id"] for b in act["briefs"])
    assert sorted(ids) == list(range(1, 42)), "story ids must be 1..41, got %s" % ids
    assert len(ids) == 41
    img = Image.new("RGBA", (W, H), PAPER + (255,))
    draw_masthead(img, data)
    draw_lead(img, data)
    draw_numbers(img, data["numbers"])
    draw_regions(img, data["region_bar"])
    for act in data["acts"]:
        draw_act_header(img, Y[act["key"] + "_head"], act["title"], act["sub"])
    nz = data["acts"][0]["hero"]
    paint_nz(img, (MARGIN, Y["nz_hero"], W - MARGIN, Y["nz_hero"] + 150))
    hero_band(img, (MARGIN, Y["nz_hero"], W - MARGIN, Y["nz_hero"] + 150),
              nz["headline"], nz["deck"], nz["src"], nz["ver"])
    draw_briefs(img, Y["act1_briefs"], data["acts"][0]["briefs"])
    uk = data["acts"][1]["hero"]
    paint_ukraine(img, (MARGIN, Y["ukraine_hero"], W - MARGIN,
                        Y["ukraine_hero"] + 156))
    hero_band(img, (MARGIN, Y["ukraine_hero"], W - MARGIN,
                    Y["ukraine_hero"] + 156), uk["headline"], uk["deck"],
              uk["src"], uk["ver"])
    draw_briefs(img, Y["act2_briefs"], data["acts"][1]["briefs"])
    nf = data["acts"][2]["banner"]
    paint_nfl(img, (MARGIN, Y["nfl_banner"], W - MARGIN, Y["nfl_banner"] + 150))
    hero_band(img, (MARGIN, Y["nfl_banner"], W - MARGIN, Y["nfl_banner"] + 150),
              nf["headline"], nf["deck"], nf["src"], nf["ver"])
    draw_briefs(img, Y["act3_briefs"], data["acts"][2]["briefs"])
    draw_saturday(img, data)
    draw_datecheck(img, data)
    draw_footer(img, data)
    check_overlaps()
    img.convert("RGB").save(out, "PNG")
    if os.environ.get("DRAW_LOG") == "1":
        with open(os.path.join(here, "boxes.json"), "w") as fh:
            json.dump(BOXES, fh)
    print("wrote %s (%d text boxes)" % (out, len(BOXES)))


if __name__ == "__main__":
    main()
