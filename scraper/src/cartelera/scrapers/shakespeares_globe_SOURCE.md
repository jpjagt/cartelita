# Shakespeare's Globe (`shakespeares-globe`)

One venue (Globe Theatre + Sam Wanamaker Playhouse; room annotation).
Category: theater.

## Data sources (the website only, since 2026-10-25)
- (TNEW `basket.shakespearesglobe.com` is no longer read: it never answers
  the production server, see below.)
- `https://www.shakespearesglobe.com/whats-on/`: cards grouped in sections;
  `section#performances` (Globe Theatre / Sam Wanamaker Playhouse) → show
  pages. Show page `.c-event-listings`: one `.c-event-listing` per day
  (`.c-event-listing__date` "FRI 6 NOVEMBER" — no year: `listing_date`
  takes the first of last/this/next year whose weekday matches and that
  isn't over a week past), one `.c-time-slot` per performance with its
  TNEW link `basket…/<prod>/<perf>` (perf id = external_id, as before), the
  time in the link ("7.30 PM") and
  `.c-event-listing__price` ("Prices: £89.00 - £29.00* | Standing: £5.00,
  £10.00" → "£5–89"; standing included, as in the masthead's own
  "Prices: £89.00 - £5.00", the fallback); `.c-event-locations` room;
  og:description / og:image.

## Curation
Only the PERFORMANCES section. Dropped: Guided Tours, Climate Action (incl.
MakeBeth, an outdoor Bankside show filed there), Family Events & Tours,
Shakespeare & Race Festival, Young People, Teacher Training/CPD, and TNEW
products not on the what's-on (Globe Exhibition, library & archive, Telling
Tales, talks, touch tours, Playing Shakespeare schools production).

## Verification (2026-10-25)
251 events (Julius Caesar 70, The Seagull 70, King John 42, Pinocchio 38,
Animals Come to the Table 30, As You Like It 1), 100% priced. DB rows = 251.
Checked: King John 2027-04-11 13:00 — page "SUN 11 APRIL 1.00 PM Prices:
£89.00 - £29.00* | Standing: £5.00, £10.00" → ours 13:00, "£5–89", SWP.

## Production (Hetzner IP), 2026-10-25
TNEW (`basket.shakespearesglobe.com` → Imperva 45.60.x) tarpits the
production server (TLS handshake, then no answer). The website answers it
and its show pages list every performance with its TNEW ids, so the module
now reads the pages alone. Local before (TNEW + pages) → after (pages):
251 → 250, all ids, dates, times, prices, rooms identical, except:
- sold out is gone: the pages have no sold-out marker (a "Limited Tickets"
  label at most), so the 4 TNEW-sold-out performances (Julius Caesar 6, 7,
  9 Nov…) now carry their price;
- As You Like It 25 Oct 13:00 (the last performance, today): the page no
  longer lists it.
Verified from prod with the new code: the same 250.
