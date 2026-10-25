# Almeida Theatre (`almeida-theatre`)

Category: theater.

## Data sources (website only)
- Calendar: `POST https://almeida.co.uk/admin/wp-admin/admin-ajax.php`
  form `action=calendar&filters=` (what `/calendar/` does) →
  `{"instances":[HTML]}`: `time[datetime="YYYY-MM-DD HH:MM:SS"]`,
  `a.c-calendar-instance__event-link` (production page), title,
  `.c-calendar-instance__access-name` (Captioned, BSL Interpreted, Audio
  Described, Relaxed Environment, Post Show Talk → annotations; Matinee and
  season names ignored), button (`a.c-btn--book` →
  `ticketing.almeida.co.uk/<prod>/<perf>`, or disabled "Sold Out").
- Production page: credits sections (`#cast-creatives`, `#creatives`,
  `#creative-team`), og:image / og:description, "Tickets £10" if stated.
- external_id: `<page slug>@<YYYY-MM-DDTHH:MM>`.
- TNEW (`ticketing.almeida.co.uk`) not read: 150 performances vs the
  calendar's 189, and it adds nothing the calendar lacks.

## Curation
The Theatre Tour is sold like a production (same TNEW product type, same
what's-on card). Kept: performances whose production page has a credits
section — the tour page has none. **Owner review**: structural but indirect.

## Price
The site publishes no full-price list for productions (only "25s & Under
£5", schools rates); price is unknown except "sold-out" and pages stating
"Tickets £10" (Angel to Olympus). Coverage 11% — a gap.

## Verification (2026-10-25)
148 events (16 sold-out, 2 priced). DB rows = 148. Checked: Beyond Caring
2027-04-24 13:00 — calendar `datetime="2027-04-24 13:00:00"`, "Sat 24 Apr
2027 1pm", Book Tickets → ours 13:00, price none.
