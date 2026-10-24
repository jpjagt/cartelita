# Cecil Sharp House (EFDSS) — source map

Venue slug: `cecil-sharp-house` (London) — 2 Regent's Park Road, Camden
NW1 7AY. Home of the English Folk Dance and Song Society; category `folk`
(list `folk`).

Data: Spektrix client `efdss` on `https://sales.efdss.org` via `_spektrix.py`
(see `spektrix_SOURCE.md`), joined to the efdss.org what's-on listing. The
module runs the helper pipeline itself (listing join → plan venues → select
→ prices → build with title/url overrides).

## The website listing

`https://www.efdss.org/whats-on` (Joomla, plain httpx) embeds every upcoming
item as `var eeVents = '<json>';` — PHP `json_encode` inside a single-quoted
JS string (so `\"`, `\\/`, `\'`; undo the JS escapes, then `json.loads`).
Per item: `id` (CMS article id), `catid` (section), `link`
(`/whats-on/26-gigs/16003-the-furrow-collective-2026`), `title`,
`bookingLink` (`/choose-seats?EventInstanceId=<numeric Spektrix instance
id>`, sometimes with a stray space; empty or external for non-Spektrix
items), `venue`. Join to Spektrix: the event's `CMSID` attribute = item `id`,
else any of the event's instance ids in a `bookingLink`.

## Curation

The box office's `TAAArtform` (Music / Dance / Children/Family / Literature)
is not enough: the weekly **Morris Dancing** classes are "Dance", and
ceilidhs/gigs like Bhangra Ceilidh, New Year's Eve Ceilidh, Festive
Gathering have no label (nor `CMSID`). The website's section is reliable:

- **26 Gigs**, **27 Dances** (ceilidhs, barn dances, balfolk, queer ceilidhs,
  family barn dance) → folk.
- Dropped: 28 Classes & Courses (Morris Dancing, English Country Dancing),
  61 Conferences & Talks (Intangible Cultural Heritage conference, A Dance
  Through History launch, Broadside Day), 66 CPD, 25 exhibitions/other, 73
  Sharp's Folk Club (not sold via Spektrix), and every Spektrix event the
  website doesn't list (e.g. the Folk Education Development Day).
- Building: seating plan → client venue "Cecil Sharp House"; others (Band on
  the Wall, Exeter Phoenix, University of Birmingham, via Zoom, "External
  Event"…) are dropped.

## Fields

- `title`: the website's title (the box office appends the season: "The
  Furrow Collective 2026" → "The Furrow Collective").
- `source_url`: `https://www.efdss.org` + the item's `link`
  (`/whats-on/<CMS id>` alone also resolves).
- `price`: price list (helper); band default = full price ("£20.50" where
  the site says "£20.50 | £12.50 Under 30 | …").
- `description`: mostly empty in Spektrix (1 of 27).

## Verification

Last verified **2026-10-24**, live: 27 performances, 25 events, 100% priced
(1 free: Winter Solstice BPOC & Global Majority Folk Club). The Furrow
Collective — Wed 28 Oct 7:30pm "£20.50" — matches its efdss.org page
("Wednesday 28 Oct 2026, 7:30pm-9:30pm, Cecil Sharp House, £20.50 | £12.50
Under 30"). Knees Up Cecil Sharp Ceilidh — Fri 20 Nov and Fri 18 Dec 8pm —
matches its page's date list. Cold-start DB: 27 rows.
