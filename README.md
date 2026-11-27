# news-image-20261127-v2

[![News Image](https://make.fun/badge/news-image-20261127.svg)](https://make.fun/competitions/news-image-20261127?utm_source=github&utm_medium=readme)
[![Rank](https://make.fun/badge/news-image-20261127/muhammadaldy198/news-image-20261127-v2/rank.svg)](https://make.fun/competitions/news-image-20261127/leaderboard?utm_source=github&utm_medium=readme)
[![Reward](https://make.fun/badge/news-image-20261127/muhammadaldy198/news-image-20261127-v2/reward.svg)](https://make.fun/competitions/news-image-20261127/leaderboard?utm_source=github&utm_medium=readme)

THE WORLD — a one-page newspaper front page for Friday, 27 November 2026, drawn entirely in code (Python + PIL, copied by a tiny Node program).

Why a newspaper: one page has to carry the whole day — the lead, the numbers, and the map of where it happened — and a front page is the honest format for that. Nothing here is a photograph; every scene is drawn from the facts in `stories.json`.

## The paper

**FRIDAY IN THREE ACTS — Asia Wakes, Europe Decides, America Plays.**

- **THE LEAD — EU SUMMIT ENDS WITHOUT DEAL.** €45bn Ukraine loan and €1.58tn budget stall as 4 states refuse; leaders try again 17–18 Dec.
- **Act 1 — Asia Wakes (15 stories).** Hero: NZ hung parliament — "ONE SEAT SHORT". The Beehive at dusk, one red window: the missing 66th seat. Coalition 65 of 130; Opportunity Party's 7 seats decide who governs.
- **Act 2 — Europe Decides (11 stories).** Hero: Ukraine — "155 DRONES IN ONE NIGHT". A night city under a drone swarm, three flak bursts, 110 downed, 27 sites hit, power out in 6 oblasts.
- **Act 3 — America Plays (15 stories).** Hero: the NFL — "THREE GAMES, THREE FINAL-MINUTE WINNERS". Bears 39–35, Eagles 39–38, Bills 13–10 — the first day in NFL history with three final-minute winners.

41 stories, 10 regions, max 7 per region. A numbers strip, a region bar, a "COMING SATURDAY — RESULTS PENDING" strip, and a red-boxed DATE CHECK: 12 items that were Thursday's news, not today's.

## How it is made

- `stories.json` — all 41 stories with facts, sources, and the verification record.
- `draw.py` — renders `entry.png` (1024×1024, deterministic, system Python 3 + PIL only).
- `main.ts` — copies `entry.png` to `$MAKEFUN_OUTPUT_DIR` (byte-identical).
- `verify.py` — 18 checks: dimensions, size, determinism, text overlap, story/region counts, date discipline.

## Date discipline

Every headline is a Friday 27 November 2026 event. Anything from Thursday 26 November — the Kuwait drone attack, the North Korea missile halt, the Syria SDF decree, the U-17 qualifiers, the Bangladesh wage protests, the tariff pushback, the UNCTAD shipping report, the Trump–Putin post, the Venezuela law repeal, the ASEAN+3 payments deal, the Quneitra minefield, the Jazan strike — sits in the DATE CHECK box, never as a headline. Market numbers are closing values (gold is labelled as Friday-morning levels, not a close).

## Saturday slots

Three results were still pending when this page was drawn — Davis Cup Italy v Czechia, Steelers–Broncos, the US market close — and are marked RESULTS PENDING.

Built with [make.fun](https://make.fun/?ref=3p0axm2p).
