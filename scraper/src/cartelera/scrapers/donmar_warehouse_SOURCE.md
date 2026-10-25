# Donmar Warehouse — source map

Venue slug: `donmar-warehouse` (London) — 41 Earlham Street, WC2H 9LX.
Category `theater` (list `theater`).

Data: Spektrix client `donmarwarehouse` via `_spektrix.py` (see
`spektrix_SOURCE.md`). Event pages come from the site's search index
(`spk.SearchIndex("donmar_main_production", …)`, Typesense — the index
behind donmarwarehouse.com/search; see `spektrix_SOURCE.md`): its 3 event
documents carry `title` + `uri` but no Spektrix id, so the join is the exact
name (`spk.title_key`: "ILFORD BOY" = "Ilford Boy"). Links only: an event
the index doesn't name, or an index failure (warning), falls back to the
Spektrix event page. (Until 2026-10-25 this was a `Site` join on
/whats-on/ + show pages.)

## Curation

`Website` attribute: **Performance** is programme. Dropped: **Development
event** — Script Conversation, "Supercool Test Event" (the web agency's test).
The client sells only five events in the window; the house runs one
production at a time.

## Quirks

- Titles are the box office's capitals ("ILFORD BOY"); the site shows "Ilford
  Boy". Kept as the source has them.
- Prices: "£15–76" — standing £15 to Price A; matches the site's price table.
- One King's Ransom performance (16 Dec, 19:00) has an all-zero price list →
  "free" (as the box office prices it).

## Verification

Last verified **2026-10-24**, live: 171 performances, 3 productions, 171/171
priced, all linked to donmarwarehouse.com. ILFORD BOY: 42 performances 24
Oct–28 Nov, 19:30 / 14:30 matinees, "£15–70" — matches
donmarwarehouse.com/events/ilford-boy (price table £70 / £55 / £30 / £20 /
£15).
Cold-start DB: same row count as the scraper output (no collapsed occurrences).

## Production (Hetzner IP), 2026-10-25
donmarwarehouse.com answers the production server with a Cloudflare managed
challenge on every path (httpx, curl_cffi and the headless browser helper
alike — no `cf_clearance` is ever issued), so the old show-page join failed
the run there. The Typesense index answers it. Verified from prod with the
new code: 169 performances, all linked to donmarwarehouse.com — identical to
the local run.
