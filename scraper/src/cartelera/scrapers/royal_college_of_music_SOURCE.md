# Royal College of Music — source map

Venue slug: `royal-college-of-music` (London) — Prince Consort Road, South
Kensington SW7 2BS. Conservatoire concerts and opera; category `classical`
(list `classical`).

Data: Spektrix client `royalcollegeofmusic` on `https://tickets.rcm.ac.uk`
via `_spektrix.py` (see `spektrix_SOURCE.md`): `spk.scrape` with
`plan_venues` and a `finish` hook that sets URL and price per performance.

## Curation

Event `Category` (values seen 2025-06 → 2027: Concert, Opera,
Masterclass/Workshop, Museum, Tour, Junior Department, Participatory Event,
Lecture/Seminar, External Hire, Prizes and competitions, blank):

- **Concert**, **Opera** → classical.
- Dropped: Masterclass/Workshop (the label mixes public masterclasses with
  participatory workshops — "Brass & Percussion with GALSI", "Clavichord
  Day" — so it can't be kept wholesale), Junior Department (the Saturday
  junior school's concerts: a department label, not an event type), Museum
  and Tour (museum tours, family museum activities, private group tours),
  Participatory Event (children's courses), Lecture/Seminar (pre-concert
  talks), External Hire, Prizes and competitions, blank.

Building: seating plan → client venue (`/plans/{id}` → `/venues`); kept when
the venue's address has the College postcode **SW7 2BS** (every RCM hall and
room: Amaryllis Fleming Concert Hall, Performance Hall, Britten Theatre,
Recital Hall, Carne Room, Performance Studio, Parry Rooms, RCM Museum, "Royal
College of Music"). The client's "Imperial College" venue (no address) is
dropped.

## Fields

- `source_url`: the performance's own page,
  `https://www.rcm.ac.uk/events/details/?id=<instance webInstanceId>` (the
  rcm.ac.uk events listing links exactly these; every instance has one).
- `price`: the price list (helper), except **pay-what-you-can** events: the
  box office's `AccountCode` attribute ends "(Box Office - PWYC)" and their
  price list is £0/£2/£5/£10/£15 with £5 as band default; those get
  `"pay what you can"` (the website says "Pay What You Can … from £2 to £15,
  with a free option"; same wording as doelen/laurenskerk).
- Descriptions and images: the client leaves them empty.

## Verification

Last verified **2026-10-24**, live: 28 performances, 21 events, 100% priced
(7 "pay what you can"). The Firebird — 29 & 30 Oct 7:30pm, Amaryllis Fleming
Concert Hall, "£20", two distinct pages — matches
rcm.ac.uk/events/details/?id=3363744 / 3363743 ("29 October 2026, 7:30pm",
"From £16.50 (incl ticket fee)": we show the top band, house rule). Chamber
Tuesdays 3 Nov 1:05pm "pay what you can" matches ?id=3825631 ("Tickets: Pay
What You Can", Performance Studio). Cold-start DB: 28 rows.
