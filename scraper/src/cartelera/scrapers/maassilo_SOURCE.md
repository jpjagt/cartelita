# Maassilo — source map

Venue slug: `maassilo` (Rotterdam). Categories **club, pop** (lists `club`,
`pop`, whitelisted). Maashaven Zuidzijde 1-2 — former grain silo; large dance
events and concerts (incl. the Now&Wow club room).

ONE source, two upstream pages (Client: httpx with the Cartelita UA):

## 1. Maassilo's own agenda (WordPress)

- `GET https://maassilo.com/agenda/` — `.x-core-card--agenda` cards: date
  `.x-core-title--pre` "24 okt" (Dutch month, no year → `infer_year`), title
  `.x-core-title--title`, link.
- `GET https://maassilo.com/wp-json/wp/v2/agenda?per_page=100&_fields=link,class_list`
  — Maassilo's own taxonomy in `class_list`: `genre-*` and `location-*`.
- One production page per card: the "Info evenement" block
  (`.x-core-intro__content` with `<strong>Label:</strong> value<br>`):
  `Tijd: 13:00 - 22:00` → start time; `Prijs: vanaf 20,-` → price.

Category from the genre: `concert`, `rock`, `hiphop` → pop; `techno`,
`house`, `hardstyle`, `hard-techno`, `drum-base`, `afro-beat` → club (no
genre → club). Annotations: genre labels + "Now&Wow" for `location-now-en-wow`.
`external_id` = `<slug>@<date>`.

## 2. Rotown's shows in the Maassilo

The concerts Rotown programmes in the Maassilo (Chef'Special, Tramhaus,
Psychedelic Porn Crumpets, Zwangere Guy …) are **not** on Maassilo's own
agenda, which is mostly commercial dance events. `rotown.parse_home(html,
venue_name="Maassilo")` on Rotown's homepage yields them (JSON-LD time/price,
Rotown's show page as `source_url`), category pop, annotation "Rotown
presents", `external_id` `rotown:<slug>@<date>`. A show on both lists (same
date + normalized title) is kept once (Maassilo's own). The Rotown source
drops non-Rotown locations, so ownership stays single.

Not covered: BIRD's Maassilo shows (Kraak & Smaak, 22 Apr 2027 — BIRD-only).

Last verified: 2026-10-14 via HTTP cross-check (Maassilo production pages:
Tijd/Prijs match; Rotown show pages: "Prijs: € 28,50" etc. match).
