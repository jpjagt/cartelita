# National Theatre (`national-theatre`)

One venue (Olivier, Lyttelton, Dorfman = one building; the auditorium is an
annotation). Category: theater.

## Data sources
- The NT **date picker** API, `https://events.nationaltheatre.org.uk/api/v1/events/<prodSeasonId>`
  (CloudFront; the booking calendar the "Dates & tickets" button opens):
  per TNEW production, `instances[]` with `_id` (the **TNEW performance id**
  = external_id, unchanged), `datetime` (UTC "…Z" → Europe/London),
  `venue` (auditorium), `bookingStatus` ("auto", "soldout"…),
  `bookingURL` (`tickets…/<prod>/<perf>`), `performanceTypes` (Preview…),
  `prices`. One request per production the listed pages link. It replaces
  the TNEW feed (`tickets.nationaltheatre.org.uk`, see tnew_SOURCE.md),
  which never answers the production server (Imperva).
- `https://www.nationaltheatre.org.uk/whats-on/` → `/productions/<slug>/`
  links. Production page: "Dates & tickets" →
  `events.nationaltheatre.org.uk/events/<prodSeasonId>` (TNEW alias host);
  JSON-LD `Event` per performance (`startDate` with offset, `location.name` =
  auditorium, `name`, `description`, `image` — truncated at 70 entries, so
  TNEW stays the performance list); `.c-event-details__venue` ("The event
  location is | Lyttelton Theatre | …"); "Ticket prices" h3 block with
  ladders ("Monday – Thursday …: £25, £36, £51, £72, £93", previews …) →
  one range over all ladder lines (booking-fee prose excluded) e.g. "£20–105".

## Curation
Kept: picker performances of a production linked from a listed production
page, playing in Olivier/Lyttelton/Dorfman (the picker's venue, else JSON-LD
location of that start, else the page's venue block). Dropped: West End transfers / Broadway / tours
(Hadestown at the Lyric, The History Boys at the Haymarket, Pride at the
Bridge, Inter Alia, Hadestown & Little Voice tours — located elsewhere and
not on the NT's TNEW), NT Live (ntlive.com) and NT at Home links, and TNEW
products with no production page: guided/backstage/costume/archive tours,
"Theatreworks" corporate training, AMEX Behind the Scenes.

## Verification (2026-10-25)
434 events, 100% priced (sold-out included). DB rows = 434. JSON-LD matched
426/434 TNEW starts. Checked: Suddenly Last Summer 2027-04-24 19:45 — site
JSON-LD "2027-04-24T19:45:00+01:00", Olivier Theatre; ladders £30…£110 /
£30…£120 / previews £25…£82 → ours "£25–120", annotation Olivier.

## Production (Hetzner IP), 2026-10-25
TNEW (`tickets.nationaltheatre.org.uk` → `natt-tnew-prod.tnhs.cloud`,
Imperva 45.60.x) completes the TLS handshake with the production server
and then never answers a request (port 80 answers its redirect instantly) —
an IP-reputation tarpit, not fixable client-side. The website and the
picker API answer prod. Local before (TNEW) → after (picker): 434 → 428.
- The picker matches the NT's public schedule (production pages' JSON-LD)
  where TNEW didn't: TNEW had 8 Cloud 9 performances (28 Dec–2 Jan, 6 of
  them "Sold out") that neither the picker nor the page lists — dropped; the
  picker has 2 Jungle Book 13:00 performances (9 Dec, 3 Feb) the page lists
  too but the TNEW feed didn't — added.
- **Sold out changes meaning**: it now comes from the picker's
  `bookingStatus = soldout` (the NT marks it on its calendar) instead of
  TNEW's "Sold out" status message. They disagree on 28 performances (22
  TNEW-sold-out now priced, e.g. most of Some Woman; 6 picker-sold-out
  previously priced, e.g. Suddenly Last Summer 19 Feb). "auto" means the
  calendar shows a booking button; live seat availability is only on TNEW.
- Everything else identical (prices, rooms, titles, URLs). Verified from
  prod with the new code: the same 428.
