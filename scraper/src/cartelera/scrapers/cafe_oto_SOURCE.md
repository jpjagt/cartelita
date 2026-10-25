# Cafe OTO — source map

Single-venue source `cafe-oto` (city `london`, category `alternative`).
Cafe OTO, 18–22 Ashwin Street, Dalston E8 — experimental music / free
improv. Own Django site, server-rendered HTML. Client: plain `httpx` with
`CARTELITA_COMPAT_UA`. Ticketing is partly DICE/Ticket Tailor (external
prices are shown on the site too).

## robots.txt (checked 2026-10-24)

`Disallow: /admin`, `/blog`; `Crawl-delay: 10`. The scraper is strictly
sequential with a 10 s pause between requests: ~5 list pages + one page per
multi-day residency (~10 in Oct 2026) ≈ 15 requests ≈ 2.5 min per run.

## List: `/events/?page=N`

12 items a page; `#iscroll_other a[href="?page=N+1"]` links the next page
(absent on the last; 5 pages, 55 items on 24 Oct 2026, to Feb 2027; capped at
15 pages). Per `div.each-activity`:

| Field | Source |
|---|---|
| date/time | first `div.each-header p`: "Saturday 24 October 2026, 7.30pm" / "…, 2–5pm" / "…, 5.30–7pm" / "…, 11am–6pm". A start without am/pm takes the end's (unless that would put it after the end). Range → `end_time`. |
| `title` | second `div.each-header` `a` text |
| `source_url`, `external_id` | the same `a[href]` = `/events/<slug>/` (per occurrence; residency nights have their own `<slug>-1`, `-2`) |
| `annotations` | `span.prefix` — the site's own presenter/series label ("Upset The Rhythm presents", "Evan Parker – Matinee Residency", "EFG London Jazz Festival", "Show + live stream"), trailing colon stripped; residency nights also get the residency's title |
| `price` | `.each-price` top-level spans: "£17" (door), "£15 Advance", "£12 (DICE)", "£10 MEMBERS", `span.stream` "£5 Live Stream". → the highest amount among non-members, non-stream spans (= the door price) via `format_gbp`; "SOLD OUT" → `sold-out`; "Free Event" → `free` |
| `image_url` | `.each-image img[src]` (absolute media.cafeoto.co.uk URL; a local placeholder for live-stream items is ignored) |

Multi-day items ("1–2 November 2026", date range, price "MORE INFO &
TICKETS") are residencies/festivals: their page (`/events/<slug>/`) lists one
`div.each-activity` per night with `div.each-header p` holding two links
(date, title) and `.event-detail-meta` prices; the first block (series pass,
no dated link) is skipped. Nights are emitted, never the range item itself.

No description (one detail fetch per event isn't worth the crawl delay).
`language`: never stated → `None`.

## Category and curation

Everything is `alternative`. The site has **no genre taxonomy**; the only
jazz signal is a festival prefix ("EFG London Jazz Festival:") on a few
items, kept as an annotation — not enough for a `jazz` category.
Structural drops (all logged in code by rule, never by title words):

- items without an event page (`href=""` — "CLOSED FOR PRIVATE FUNCTION");
- price span "cancelled" (also for a residency night);
- prefix starting with "OFFSITE" (the site's label for shows at other
  venues, e.g. "OFFSITE – LCMF 2026:", "OFFSITE SHOW").

Kept although not concerts, because the venue lists them as its programme
and there's no structural signal: talks/book launches ("Globe Unity 60 – an
illustrated talk"), the Winter Fair.

## Quirks

- Some sold-out shows say so only in residency prose ("Please note these
  shows are SOLD OUT", Grouper 18–19 Nov) with no price spans → `None`.
- The list includes yesterday's item until the day rolls; events before
  today (Europe/London) are dropped.

## Verification

Last verified: **2026-10-24 via HTTP cross-check.** Live scrape: 67 events,
24 Oct 2026 → 19 Feb 2027 (incl. 31 residency nights from 13 multi-day
items); price 65/67 (3 sold-out, 1 free; the 2 without are the Grouper
nights above), start_time 67/67, image 66/67. Independent check: regex
over the raw page-1 HTML (not the scraper's code) → first 6 items' date,
title, link and first £ amount agree (BBBBBBB £17, Carl Stone £17, SPACE
£19, Hastings of Malawi £14, The Handover £18; the 29–31 Oct festival
expanded to 3 nights at £22 each, matching its page).
