# KABUL à GoGo — source map

Venue slug: `kabul-a-gogo` (Utrecht; module `kabul.py`). Categories **club**,
**alternative**; lists whitelisted. Gietijzerstraat 3, Werkspoorkwartier.

Client: plain httpx with the Cartelita UA. 1 + N detail requests (N≈8).

## List URL

`https://www.kabulagogo.nl/` — Webflow; the homepage server-renders the full
agenda collection (`.agenda-collection_wrapper`).

| Field | Source |
|---|---|
| `external_id` | URL slug `/events/<YYYYMMDD[-n]>` |
| `title` | `h4` |
| `start_date` | `.div-block-23 .heading-style-h2` (visible ones): "Friday , 16 October 2026" |
| rooms | `.area_tags .label_regular` (Abu, Teatro, Zohal, Layla, …) → annotations |
| genres | `.genre_tags:not(.w-condition-invisible) .label_regular` → annotations |
| `category_slugs` | genres Live music/Performance/Poetry/triphop/experimental → alternative; any other genre (house, techno, Club Night, dub, …) or none → club |
| `price` | only the venue's "Free Entry" label → `"free"`; otherwise None (tickets on weticket.io, prices not server-rendered) |
| `start_time` | event page rich text (`.richtext-regular`, then `.text-size-regular`): first "22:00–04:00" range, else "From 4PM" |

## Exclusions

- Room labels naming none of KABUL's rooms → KABUL programming hosted
  elsewhere (Centraal Museum "Centraal Laat").
- Genre `Workshop` (STOMP queer line-dance class).
- Genre `hits`: the label the venue uses only for its recurring Muziekbingo
  XXL nights (a touring third-party sing-along bingo format, 5 dates).

Kept: Teatro Danscafé (weekly free dance café with named DJs/collectives).

## Verification

Last verified: **2026-10-14 via HTTP cross-check.** Live: 8 events,
2026-10-16 → 2026-11-14; time 7/8 (Guitig: no time in the text), price 2/8
(free). Independent check: start times vs the venue's WeTicket shop listing
(`kabulagogo.weticket.io`) — the 3 events listed there agree (22:00); Guitig
is listed there at 16:00 while the site text states none.
