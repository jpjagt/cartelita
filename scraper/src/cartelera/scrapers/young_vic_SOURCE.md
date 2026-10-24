# Young Vic — source map

Venue slug: `young-vic` (London) — 66 The Cut, SE1 8LZ. Category `theater`
(list `theater`).

Data: Spektrix client `youngvic` (`https://system.spektrix.com/youngvic/api/v3`,
plain httpx — the API has no Cloudflare) via `_spektrix.py` (see
`spektrix_SOURCE.md`). **No site join:** youngvic.org is behind Cloudflare
(curl_cffi gets through), but its show pages carry no Spektrix ids — the
performance list is loaded client-side from the site's own API
(`/api/attendable/v1/instances/`, `booking_url` per instance) — and the
what's-on page sits behind Cloudflare for plain httpx. Events link to the client's Spektrix event
page (`…/youngvic/website/EventDetails.aspx?EventId=<n>`, 200).

## Curation

- **`SupplementaryEvent` = true → dropped**: show programmes (Eurotrash /
  dissent / Girls programme), Girls Playtext, assisted-listening device and
  audio-description headset (one "instance" per performance — 311 and 32),
  Free Touch Tour.
- **`Venue` (the room) must be one of Main House, The Maria Theatre, The
  Clare, Outside the Young Vic.** This drops "Temporary Priority Test" (a
  box-office test with no attributes at all). "Outside the Young Vic" is
  Darkfield's *Eulogy* (an immersive audio show in a shipping container in
  the forecourt, 215 performances, listed on youngvic.org/whats-on/eulogy/).
  The Clare (the second studio) has no events in the window but is a real
  room.
- `Genre` (New writing / Studio / Musical - star casting …) is not needed
  and is missing on Eulogy and Eurotrash.

## Quirks

- Titles are the box office's capitals ("EUROTRASH", "GIRLS"); the site
  shows "Eurotrash". Kept as the source has them (no shared de-shouting
  helper yet).
- Prices: each band's default includes a £12 "Lucky Dip" band, so Main House
  shows read "£12–80". The site shows no prices in its HTML.
- `annotations`: access needs live in string instance attributes
  (`Accessibility`, `Accessibility2`: "Audio described", "Captioned", "BSL",
  "Relaxed", "Touch Tour"; `PerformanceInformation`: "English Surtitles",
  "Press Night", "£12 first preview"), taken verbatim (`annotation_attrs`).
  The client has no boolean access flags.

## Verification

Last verified **2026-10-24**, live: 414 performances, 7 shows, 413/414
priced. GIRLS: 32 performances 24 Oct–21 Nov, 20:00 evenings and 15:00
Wed/Sat matinees, The Maria Theatre — matches youngvic.org/whats-on/girls/
("22 OCT - 21 NOV", "Monday - Saturday, 8pm | Wednesday & Saturday matinees,
3pm", The Maria Theatre). EULOGY 24 Mar–17 Apr matches "Wed 24 Mar – Sat 17
Apr 2027".
Cold-start DB: same row count as the scraper output (no collapsed occurrences).
