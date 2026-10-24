# Smith Square Hall (Sinfonia Smith Square) — source map

Venue slug: `smith-square-hall` (London) — Smith Square, Westminster SW1P 3HA
(formerly St John's Smith Square; the hall and its crypt are run by Sinfonia
Smith Square). Categories `classical`, `jazz`, `kids`, each its own list,
whitelisted to that category.

Data: Spektrix client `sinfoniasmithsquare` on
`https://checkout.sinfoniasmithsq.org.uk` via `_spektrix.py` (see
`spektrix_SOURCE.md`). No site join: sinfoniasmithsq.org.uk loads
performances by script (admin-ajax) and neither its HTML nor its WP REST
`event` posts carry Spektrix ids, and `webUrl` is empty, so events link to
the Spektrix event page (`…/website/EventDetails.aspx?EventId=…`, 200).

## Curation (the client's own attributes)

1. `Venue` must be "Smith Square Hall" or "Smith Square Crypt". Dropped:
   Westminster Abbey (two Christmas concerts it sells there: another
   building) and items with no venue (the "Wild Arts post-show reception"
   upsell).
2. Category:
   - `Type` Jazz, or `Series` "Jazz in the Crypt" → `jazz`;
   - `Type` Orchestral / Choral / Chamber / Organ / Vocal / Opera → `classical`;
   - `Type` "Family concerts and events" (Snowman / Wallace & Gromit live in
     concert, Gabrieli Roar) → `classical` + `kids`;
   - no `Type` but a house `Series` (Lunchtime Concerts, London Festival of
     Baroque Music, Christmas Festival, Sinfonia Smith Square Fellowship) →
     `classical` (e.g. Winterreise with Roderick Williams);
   - neither label → dropped (2026-10: Alexei Tartakovsky recital, LMP
     "Tasting Notes: Bordeaux", Sanctuary, Siglo de Oro, an external
     "Vivaldi, The Four Seasons" — unlabelled external hires; we can't tell
     programme from rental without a label).

Labels are taken as given: "Martin Taylor & Guy Barker – The Spirit of
Django" is `Type` Orchestral → classical; "Red Events – Hayao Miyazaki's
Dreams" (Orchestral, external promoter) is kept.

## Quirks

- Prices are real seating bands (Price Band A/B/C, Gallery restricted view):
  £25/35/45 → "£45" (2x rule); the site says "Price £25-£45".

## Verification

Last verified **2026-10-24**, live: box office 68 events / 73 instances →
kept **60 events / 65 performances** (2026-10-24 → 2027-04-10), 65/65 priced;
classical 57, classical+kids 5, jazz 3. All link to the Spektrix page.
Field check, LFBM 2026: Bach Orchestral Suites vs
sinfoniasmithsq.org.uk/event/bach-orchestral-suites/: Sat 24 Oct 19:30 (also on
the Spektrix page: "24 Oct 2026 - 19:30 (Sat)"), "£45" (site: "Price band A:
£45, B £35, C £25"), Smith Square Hall — match.
Cold-start DB: 65 rows.
