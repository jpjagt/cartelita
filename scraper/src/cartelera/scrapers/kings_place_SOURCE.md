# Kings Place — source map

Venue slug: `kings-place` (London) — 90 York Way, King's Cross N1 9AG.
Categories `classical`, `folk`, `jazz` (lists of the same names, each
whitelisted to its category).

Data: Spektrix client `kingsplace` on
`https://ticketing.purchase.kingsplace.co.uk` via `_spektrix.py` (see
`spektrix_SOURCE.md`), joined to the kingsplace.co.uk what's-on listing:
`spk.scrape` with the listing join as `prepare` (`Programme.prepare`,
before curation) and title/url overrides from the joined card.

## The website listing

`https://www.kingsplace.co.uk/whats-on/` and `/whats-on/page/N/` (9 pages,
24 cards each, 203 cards on 2026-10-25; follow while the page links
`/page/N+1/`). **Cloudflare 403s httpx; curl_cffi (`impersonate=True`)
gets 200.** One card per performance: `.grid-item[data-id]` where
`data-id` is the full Spektrix **instance** id (140 cards) or **event**
id (14 cards); card classes = genre + series slugs (`online-events` marks
streams); `.grid-item__title`; the "More info" link
`https://www.kingsplace.co.uk/whats-on/<genre>/<slug>/`. No show pages are
fetched.

## Curation (the URL path's genre)

| Path segment | → |
|---|---|
| `classical` | classical |
| `folk` | folk |
| `jazz` | jazz |
| `contemporary` (Songlines Encounters world music, (Re)Sounding India, crossover pianists), `family` (Aurora Orchestra family concerts, barn dance), `words`, `comedy`, `podcast`, festival-only segments (`origins-unwrapped`) | dropped |

Also dropped: cards classed `online-events` (streams), and every Spektrix
event the website doesn't list (Dec Test Events, "Secure My Booking",
"Rotunda Restaurant", "Songs of the Heart" on 2026-10-25). The Spektrix
client has no genre attribute (`Ticketsforgoodevent`, `ImportId` only).

## Fields

| Field | Source |
|---|---|
| `title` | the card title (the box office is terser: "Royal Northern Sinfonia" vs the site's "Vivaldi's Four Seasons, with Maria Włoszczowska & Royal Northern Sinfonia") |
| `source_url` | the card's event page |
| `start_*`, `price`, `external_id`, `description`, `image_url` | Spektrix (helper): instance `start`, price list band defaults ("£28–£35" on the site → "£35", 2x rule), instance id |

## Verification

Last verified **2026-10-25** via HTTP cross-check (curl_cffi) with the
event pages: 112 performances (48 classical, 36 folk, 28 jazz), 100%
priced. Siobhan Miller Band — page "Date: Thu 5 Nov, Start time: 8pm,
Venue: Hall One, Price: £21" → scraper folk, 5 Nov 20:00 "£21"; Royal
Northern Sinfonia — "Sun 25 Oct, 3pm, £28-£35" → classical 15:00 "£35";
Bill Laurance (jazz) "£25/£40" → "£40". Cold-start DB: rows = scraper
output (see the batch report).
