# The Old Vic (`old-vic`)

Category: theater (owner decision 2026-10-24: in).

## Data sources
- TNEW `my.oldvictheatre.com` (Queue-it safetynet; plain session passes):
  performances, sold out, perf id; `productTypeName` names the access
  provision (Captioned, Audio Described, BSL Interpreted, Relaxed
  performance) → annotation.
- `https://www.oldvictheatre.com/productions/` → `/stage/<slug>/` pages;
  "Book Now" → `my.oldvictheatre.com/events/<prodSeasonId>` (join); heading
  `.event-hero-right__heading`; "Tickets" segment
  (`.essential-information__segment-text`) "Previews £19.50–£81.50, Off-Peak
  …, Peak £19.50–£91.50" → "£19.50–91.50" (access rate excluded); og meta.
- (`/whats-on` is a 404; WP REST is closed.)

## Curation
Listed /stage/ productions with a TNEW production. Dropped: Christmas
Storytelling (listed, TNEW product type 4, but its page has no TNEW link to
join — a one-off kids' storytelling).

## Verification (2026-10-25)
76 events (A Christmas Carol 67, Martin Guerre 9), 100% priced. DB rows = 76.
Checked: A Christmas Carol 2027-01-09 — TNEW "Saturday 09 Jan 2027 2:00pm /
7:00pm"; page "Tickets Previews £19.50–£81.50, Off-Peak £19.50–£81.50, Peak
£19.50–£91.50" → ours 14:00 & 19:00, "£19.50–91.50".

## Production (Hetzner IP), 2026-10-25 — does not work
`my.oldvictheatre.com` (→ `olvc-tnew-prod.tnhs.cloud`, Imperva) tarpits the
production server: TLS handshake, then no answer to any request (httpx,
curl_cffi, the headless browser helper; 45–60 s timeouts). The website
answers prod, but carries no per-performance data: the `/stage/` pages give
a run, a price ladder, the access performances in prose and a "Book Now"
link to the TNEW calendar; no JSON-LD events, no API (WP REST closed), no
other open listing. Generating dates from the run + weekly pattern would be
recurrence expansion and guesswork (no sold-out, no exceptions) — not done.
Left unchanged: the source fails in production until the scrape can reach
TNEW from another egress (or the Old Vic/Tessitura allowlist the server).
