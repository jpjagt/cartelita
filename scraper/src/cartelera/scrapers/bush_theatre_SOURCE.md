# Bush Theatre — source map

Venue slug: `bush-theatre` (London) — 7 Uxbridge Road, W12 8LJ. New writing;
category `theater` (list `theater`).

Data: Spektrix client `bushtheatre` on its custom domain
(`https://tickets.bushtheatre.co.uk/bushtheatre/api/v3`) via `_spektrix.py`
(see `spektrix_SOURCE.md`). Show pages are joined in
(`Site("https://www.bushtheatre.co.uk/whats-on/", …/event/<slug>/)` — note
the `www.` host: the bare domain's what's-on page links nothing); each
embeds its performances' full Spektrix ids.

## Curation

`WebsiteCategorisation` (the website's own split): **Production** is
programme. Dropped: **Supplementary** — Pre-order Drinks (195 instances),
Audio Description Headset, Captioning Facilities, Touch Tour, Touch Tour
(Studio). `Genre` is "New Writing" on every production; `TicketVenue` is the
room (Holloway Theatre / Studio), both in the one building.

## Quirks

- A show page in its last week can show no booking ids (The Hungry Ghost,
  2026-10-24): its events fall back to the Spektrix event page.
- Prices: "£10–45" (Holloway Theatre bands), "£25" (Studio; previews £15/£20).

## Verification

Last verified **2026-10-24**, live: 199 performances, 7 shows, 199/199
priced; 6 of 7 linked to bushtheatre.co.uk. ATTENTION: 39 performances 19
Nov–23 Dec, Studio, 20:00 / 15:00 matinees, previews £15/£20, then £25 —
matches www.bushtheatre.co.uk/event/attention/ ("Studio", "19 Nov to 23 Dec",
"£15.00 to £25.00").
Cold-start DB: same row count as the scraper output (no collapsed occurrences).
