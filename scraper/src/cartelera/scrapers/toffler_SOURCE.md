# Toffler — source map

Venue slug: `toffler` (Rotterdam). Category **club** (list `club`). Weena-Zuid
33 — techno/house club in a former pedestrian tunnel.

Site: `https://www.toffler.nl/` (Elementor WordPress). Client: httpx with the
Cartelita UA. One request: `GET https://www.toffler.nl/club/` — a hand-edited
"Upcoming events" block (~8 nights ahead).

## Fields

Per Elementor container holding a text widget matching "Friday 16.10":

| Field | Source |
|---|---|
| `start_date` | "Friday 16.10" (day.month, no year → `infer_year`) |
| `title` | the next text widget ("TOFFLER Presents …") |
| `description` | "Line-up: " + the third text widget |
| `source_url` | the club page (no per-night pages; tickets on Paylogic) |
| `external_id` | `toffler@<date>` |
| `start_time`, `price` | None — not stated per night (the FAQ's "Doors open at 23:00 till 05:00. Please always check the event opening times" is a house default); prices only in Paylogic's JS shop |

The `/indoor-festival/` and `/festival-2/` pages (Toffler's summer festival)
are not scraped.

Last verified: 2026-10-14 via HTTP cross-check (club page text: 8 dates and
titles match).
