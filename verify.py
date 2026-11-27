"""news-image-20261127 v2 — pre-submit verifier (Kirana, Hunter Office).

18 checks: gate (size/bytes/format), determinism, image signal, text
overlap, story counts, region caps, tag uniqueness, src/ver labels, fit,
date discipline, thumbnail signal. Run with system python3 from the entry
directory.
"""
import hashlib
import json
import os
import subprocess
import sys

from PIL import Image, ImageStat

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(HERE, "entry.png")
STORIES = os.path.join(HERE, "stories.json")
DRAW = os.path.join(HERE, "draw.py")
PYTHON = sys.executable
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + ((" — " + str(detail)) if detail else ""))
    return ok


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def render_to(path):
    env = dict(os.environ)
    env["DRAW_LOG"] = "1"
    r = subprocess.run([PYTHON, DRAW, path], env=env, capture_output=True,
                       text=True, cwd=HERE)
    assert r.returncode == 0, "draw.py failed: " + r.stdout + r.stderr
    return path


def main():
    with open(STORIES, encoding="utf-8") as fh:
        data = json.load(fh)

    # 1. entry.png exists
    check("01 exists", os.path.exists(ENTRY))

    # 2. dimensions 1024x1024
    im = Image.open(ENTRY)
    check("02 dimensions 1024x1024", im.size == (1024, 1024), im.size)

    # 3. bytes <= 1 MiB
    size = os.path.getsize(ENTRY)
    check("03 bytes <= 1 MiB", size <= 1048576, "%d bytes" % size)

    # 4. PNG magic bytes
    with open(ENTRY, "rb") as fh:
        magic = fh.read(8)
    check("04 PNG magic", magic == b"\x89PNG\r\n\x1a\n")

    # 5. determinism: two fresh renders byte-identical, and committed
    #    entry.png matches a fresh render
    p1 = os.path.join(HERE, "verify-tmp-1.png")
    p2 = os.path.join(HERE, "verify-tmp-2.png")
    try:
        render_to(p1)
        render_to(p2)
        s1, s2 = sha256(p1), sha256(p2)
        check("05 determinism (2 renders)", s1 == s2, s1[:12])
        check("05b committed == fresh render", sha256(ENTRY) == s1,
              sha256(ENTRY)[:12])
    finally:
        for p in (p1, p2):
            if os.path.exists(p):
                os.remove(p)

    # 6-8. image signal (calibrated to this design: dark hero art is
    #    intentional; binding guard is dark fraction <= 0.25)
    gray = im.convert("L")
    st = ImageStat.Stat(gray)
    mean, std = st.mean[0], st.stddev[0]
    check("06 gray mean 100-245", 100 <= mean <= 245, round(mean, 1))
    check("07 gray stddev >= 25", std >= 25, round(std, 1))
    hist = gray.histogram()
    dark = sum(hist[:40]) / (1024 * 1024)
    check("08 dark fraction <= 0.25", dark <= 0.25, round(dark, 3))

    # 9. text-box overlap (boxes.json written by draw.py with DRAW_LOG=1)
    boxes_path = os.path.join(HERE, "boxes.json")
    check("09 boxes.json present", os.path.exists(boxes_path))
    bad = []
    if os.path.exists(boxes_path):
        with open(boxes_path, encoding="utf-8") as fh:
            boxes = json.load(fh)
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                ox = min(a[3], b[3]) - max(a[1], b[1])
                oy = min(a[4], b[4]) - max(a[2], b[2])
                if ox > 0 and oy > 0:
                    bad.append((a[0], b[0]))
    check("09b zero text overlap", not bad, bad[:3])

    # 10. masthead date exact
    check("10 masthead date", data["meta"]["date_line"] ==
          "FRIDAY, 27 NOVEMBER 2026", data["meta"]["date_line"])

    # 11. stories: 41, ids 1..41 (lead counts as story 16)
    ids = [data["lead"]["id"]]
    for act in data["acts"]:
        if "hero" in act:
            ids.append(act["hero"]["id"])
        ids.extend(b["id"] for b in act["briefs"])
    check("11 stories 41, ids 1..41", sorted(ids) == list(range(1, 42)) and
          len(ids) == 41, len(ids))

    # 12. regions: 10 regions, max <= 7
    from collections import Counter
    regions = Counter()
    regions[data["lead"]["region"]] += 1
    for act in data["acts"]:
        if "hero" in act:
            regions[act["hero"]["region"]] += 1
        for b in act["briefs"]:
            regions[b["region"]] += 1
    check("12 regions 10, max <= 7", len(regions) == 10 and
          max(regions.values()) <= 7, dict(regions))

    # 13. tags unique across all 41 stories; every story carries a named
    # source + a verification label from the allowed set (D8)
    tags = []
    stories = [data["lead"]]
    for act in data["acts"]:
        if "hero" in act:
            tags.append(act["hero"]["tag"])
            stories.append(act["hero"])
        tags.extend(b["tag"] for b in act["briefs"])
        stories.extend(act["briefs"])
    bad_label = [s["id"] for s in stories
                 if "src" not in s or "ver" not in s or
                 s["ver"] not in ("OFFICIAL", "REPORTED", "CLAIM", "ONGOING")]
    check("13 tags unique + src/ver labels", len(tags) == len(set(tags)) and
          not bad_label, "%d tags, %d unique; bad labels: %s" %
          (len(tags), len(set(tags)), bad_label))

    # 14. briefs fit: headline at 11px bold + deck line (src + ver + deck)
    # at 8px, both inside a 328px column (D8/D9)
    from PIL import ImageFont
    f11 = ImageFont.truetype(
        "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf", 11)
    ftag = ImageFont.truetype(
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", 11)
    f8 = ImageFont.truetype(
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", 8)
    too_long = []
    for act in data["acts"]:
        for b in act["briefs"]:
            w = ftag.getbbox(b["tag"] + " — ")[2] + \
                f11.getbbox(b["headline"])[2]
            if w > 328:
                too_long.append((b["tag"], w))
            line2 = "%s · %s — %s" % (b["src"], b["ver"], b["deck"])
            w2 = f8.getbbox(line2)[2]
            if w2 > 328:
                too_long.append((b["tag"] + " deck", w2))
    check("14 briefs + decks fit", not too_long, too_long)

    # 15. date discipline blocks: 20 DATE CHECK items, 3 Saturday slots
    dc = data["datecheck"]["items"]
    sat = data["saturday"]
    check("15 datecheck 20 + saturday 3 pending",
          len(dc) == 20 and len(sat["items"]) == 3 and
          "PENDING" in sat["header"], (len(dc), len(sat["items"])))

    # 16. thumbnail 300px still carries signal
    small = im.convert("L").resize((300, 300))
    sstd = ImageStat.Stat(small).stddev[0]
    check("16 thumbnail 300px stddev >= 15", sstd >= 15, round(sstd, 1))

    failed = [c for c in CHECKS if not c[1]]
    print("----")
    print("%d/%d PASS" % (len(CHECKS) - len(failed), len(CHECKS)))
    if failed:
        print("FAILED: " + ", ".join(c[0] for c in failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
