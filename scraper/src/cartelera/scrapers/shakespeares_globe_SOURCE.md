# Shakespeare's Globe (`shakespeares-globe`)

One venue (Globe Theatre + Sam Wanamaker Playhouse; room annotation).
Category: theater.

## Data sources
- TNEW `basket.shakespearesglobe.com` (Queue-it safetynet; plain session
  passes): performances, sold out, perf id.
- `https://www.shakespearesglobe.com/whats-on/`: cards grouped in sections;
  `section#performances` (Globe Theatre / Sam Wanamaker Playhouse) → show
  pages. Show page `.c-event-listings`: per performance a TNEW link and
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
