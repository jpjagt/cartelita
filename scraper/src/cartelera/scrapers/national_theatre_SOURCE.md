# National Theatre (`national-theatre`)

One venue (Olivier, Lyttelton, Dorfman = one building; the auditorium is an
annotation). Category: theater.

## Data sources
- TNEW `tickets.nationaltheatre.org.uk` (tnew_SOURCE.md): every performance
  (date/time, sold out, perf id = external_id).
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
Kept: TNEW performances of a production linked from a listed production page,
playing in Olivier/Lyttelton/Dorfman (JSON-LD location of that start, else
the page's venue block). Dropped: West End transfers / Broadway / tours
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
