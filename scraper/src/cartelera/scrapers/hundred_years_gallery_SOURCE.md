# Hundred Years Gallery — source map

Single-venue source `hundred-years-gallery` (city `london`, category
`alternative`). Hundred Years Gallery, 13 Pearson Street, Hoxton E2 8JD — a
small gallery with a free-improv / experimental music programme (Steve
Noble, Mark Wastell's monthly "Duo Intern" residency, the KNOT series), plus
exhibitions, book events and performance art.

Own WordPress site. **HTTPS times out** on this host (checked 2026-10-24);
plain `http://` works and is what the site links to itself. Client: `httpx`
with `CARTELITA_COMPAT_UA`; robots.txt only disallows `/wp-admin/`.

## List: `http://hundredyearsgallery.co.uk/events/upcoming/`

One page, every upcoming item as `h4.petitle a`:
"Type : Title. Weekday Nth Month HH:MM", e.g.
"Music : KNOT #14 : Xiang / Fabian Neubauer / Yoni Silver / Zheng Hao. Saturday 7th November 19:30".

| Field | Source |
|---|---|
| type | text up to the **first** colon ("Music", "Residency", "Music / Poetry", "Exhibition", "Book", "Books", "Performance") |
| `title` | after the type, up to the trailing ". Weekday …" (titles may contain colons) |
| `start_date` | "Saturday 7th November" — no year: the year (this/next) on which that date is the stated weekday, not before today − 7 days |
| `start_time` | "19:30" / "15.00" (doors/start as listed). An hour 1–8 is read as pm ("4.30" afternoon sessions). |
| `source_url`, `external_id` | the item's post URL / its slug |
| `annotations` | the type label |

## Post (one per kept item, ≤3 concurrent)

| Field | Source |
|---|---|
| `description` | `.entry-content` paragraphs |
| `price` | prose: "free event" / "free entry" / "entry free" → `free` (wins over a "suggested donation £5"); else the highest £ amount on a door/entry/ticket/cash/£ line ("Doors 7.30 \| music 8pm \| £10 cash door" → `£10`); nothing stated → `None` |
| `image_url` | first `img` in `.entry-content` |

## Curation (the site's own type prefix)

Kept: types containing **Music** (incl. "Music / Poetry") or **Residency** —
including the monthly "Residency : Collective Drawing Session" (live
electronic improvisation by the resident musician with an open drawing
session; it's in the residency strand). Dropped: Exhibition, Book/Books,
Performance (live-art group), and untyped items ("Dissidences 7. Sound,
voice, word." — a sound-poetry series without a type prefix).

Category: `alternative`, not `jazz` — the programme is free improvisation,
electroacoustic and experimental music (Wastell, Noble, KNOT), London's
"experimental" circuit next to Cafe OTO, not jazz clubs.

## Verification

Last verified: **2026-10-24 via HTTP cross-check.** Live scrape: 17 events
(24 Oct → 12 Dec 2026; 26 items on the page, 9 dropped by type); price 11/17
(3 free residencies, 8 × £10–13), description 15/17, image 16/17. The 6
without a price state none in their post (checked by grepping each post for
£/free/door/ticket/entry). Independent check: a throwaway regex over the
fresh raw list HTML (not the scraper's code) found 26 items, 17 starting
with Music/Residency, whose (day, month, time) keys are exactly the
scraper's 17;
Bismillah 29 Oct 19:30 "£10 cash door" → `£10`; Mark Wastell 31 Oct 16:00
"Free event" → `free`.
