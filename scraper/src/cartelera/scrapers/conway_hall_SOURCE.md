# Conway Hall (Sunday Concerts) — source map

Venue slug: `conway-hall` (London) — 25 Red Lion Square, Holborn WC1R 4RL.
Category `classical` (list `classical`). Only the Sunday Concerts series
(chamber music since 1887, Sundays 6.30pm, Main Hall).

Data: Ticketsolve feed `https://conwayhall.ticketsolve.com/shows.xml` via
`_ticketsolve.py` (see `ticketsolve_SOURCE.md` for fields and prices).

## Curation

`event_category` = **Sunday Concerts** → classical (8 concerts on
2026-10-25; every one also tagged `sundayconcerts`). Dropped, by the feed's
own category:

- Talks & Debates (Conway Hall Ethical Society talks, Intelligence Squared
  hires), Film & Performance (Thinking in Frames);
- Music — outside promoters hiring the hall (The Golden Fountain; "Winter
  Carols by Candlelight" by Electric Voice Theatre);
- uncategorised items: the News Club, an Intelligence Squared hire, and the
  RNCM **Lunchtime Recitals** (tag `rncm`) — a possible later addition if
  the hall gives them a category.

Online streams of talks are dropped by the helper.

## Fields

As the helper; price = the Standard ticket ("Supporter £20 · Standard £14 ·
Student/NHS £9 · Living Support £6 · Under 18s free" → "£14"; the website
adds a £2 venue levy, not included).

## Verification

Last verified **2026-10-25** via HTTP cross-check with conwayhall.org.uk:
8 concerts, 100% priced. Aida Piano Trio — site "1st November 2026 ·
6:30pm - 8:30pm", "In advance: Supporter £20 • Standard £14 …" → scraper 1
Nov 18:30 "£14". The site's "Halcyon Quartet" page now announces Ruth
Rogers & Martin Cousin (29 Nov), as the feed does. Cold-start DB: 8 rows.
