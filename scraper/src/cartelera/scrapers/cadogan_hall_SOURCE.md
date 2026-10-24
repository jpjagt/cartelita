# Cadogan Hall — source map

Venue slug: `cadogan-hall` (London) — 5 Sloane Terrace, Chelsea SW1X 9DQ.
RPO's home; choral, opera, London Jazz Festival; also a rental hall.
Categories `classical`, `jazz`, `folk`, `kids`, `film`, each its own list
whitelisted to that category.

Data: Spektrix client `cadoganhall` on `https://tickets.cadoganhall.com` via
`_spektrix.py` (see `spektrix_SOURCE.md`).

## Curation (the client's own genre labels)

`Genre1` is the main genre, `Genre2` a qualifier (`WebsiteCategory` is too
sparse to use; `Type` is always empty).

| Genre1 | → | except |
|---|---|---|
| Orchestra, Choral, Opera | classical | Genre2 Tribute; Choral+Film (Gareth Malone sing-along); Choral+Gospel (Kingdom Choir) |
| Family | classical + kids | (The Snowman in Concert) |
| Jazz | jazz | Genre2 Tribute; Jazz+Orchestra (RPO "'S Wonderful" love songs) |
| Folk | folk | Genre2 Tribute (Joni Mitchell tribute) |
| Film | film only with Genre2 Orchestra (silent films with live score: Frankenstein, Metropolis) | Film+Big Band (Bond music concert) |
| Pop, Rock / Country, Talk, Comedy, Musical Theatre, Dance, blank | dropped | |

Blank-genre items are the ancillaries ("Secure My Booking", programme
vouchers, Glass of Prosecco ×107, Snowman toys, VIP packages, meet & greet)
— and, a loss, the free "OTL" (Out to Lunch) foyer jazz gigs and "The
Mozartists – The Truth About Love", which carry no genre either.

Labels taken as given (kept): Viennese Christmas Spectacular by Candlelight
and A Night at the Opera by Candlelight (Orchestra/Opera), The Rat Pack at
Christmas (Jazz/Christmas), Ledisi (Jazz/Blues & Soul), Colosseum + Soft
Machine (Jazz/Rock).

## Fields / quirks

- `source_url`: the event's `webUrl` (the hall's own show page; filled for
  ~75% of kept performances; stripped — one has a trailing space), else the
  Spektrix event page. Show pages do embed `/book/<instance id>`, but no
  Site join (reconsidered 2026-10-24): the what's-on page's dead show-page
  links (e.g. `/whats-on/colosseum-soft-machine/` → 404) no longer fail the
  shared join (it skips them), but the listing is paginated
  (`/whats-on/page/<n>/`) and the join would fetch ~180 show pages per run
  to link the ~17 performances without a webUrl (RPO and ZIOS concerts,
  Ledisi…) — not worth it while webUrl covers ~75%.
- Prices: seating bands A–E ("£18–60"); the site's "Prices from £34.50 (£30 +
  £4.50 transaction fee)" is the lowest band plus fee.

## Verification

Last verified **2026-10-24**, live: box office 112 events / 354 instances →
kept **62 events / 71 performances** (2026-10-25 → 2027-04-22), 71/71 priced;
classical 44, jazz 20, film 3, folk 2, classical+kids 2; 53 linked to
cadoganhall.com, 18 to the Spektrix page.
Field check, LJF: Gerald Clayton Trio vs
cadoganhall.com/whats-on/ljf26-gerald-clayton-trio/: "Saturday 21 November
2026, 7.30pm", "Prices from £34.50 (£30.00 + £4.50 transaction fee)"; ours
2026-11-21 19:30 "£40" (bands £30/35/40 → top price under the 2x rule) —
match.
Cold-start DB: 71 rows.
