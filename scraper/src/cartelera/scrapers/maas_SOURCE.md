# maas — source map

Maas theater en dans (maastd.nl): a youth theatre/dance company with its own
stage, the Maaspodium. Source slug `maas`, one venue `maaspodium`.
Client: plain httpx, UA `Mozilla/5.0 (compatible; Cartelita
(+https://cartelita.co))`.

## Data

1. `GET https://www.maastd.nl/ajax/showsearch/?culture=nl-NL&showLabels=&showPeriod=all&searchTerm=&page=1&take=1000&orderBy=&isMobile=false&isHomepage=false`
   — the agenda page's XHR (`/js/base.js`, `showResults`). `Shows[]`, one per
   performance (~220, ~1.5 MB):
   - `DatumTheaterDisplay` "2027-01-10 14:00:00" → date/time
   - `ShowZaal.IsMaaspodium` → keep only true (Maas tours NL; its Rotterdam
     dates at Theater Rotterdam/Zuidplein belong to those venues' sources)
   - `TitelMetLeeftijd` → title (as printed: "DAG POES / 4+"; whitespace collapsed)
   - `Leeftijd` "4+" / "1,5+" / "Jongeren en volwassenen" → kids + annotation
   - `Uitverkocht` → price "sold-out"; `Geannuleerd` → skipped
   - `LanguageNoProblem` → language "Language no problem"
   - `EventId` → external_id (per occurrence); `absoluteUrl` → source_url
   - `Subtitel` → description; `<img src>` in `AfbeeldingHtmlString` → image
   School performances ("Schoolvoorstelling") are not in this feed.
2. Production page (`ShowUrl`, one per production, ~75 requests):
   `.showheader__specs--types strong` "Fysiek theater, Danstheater, Dans" →
   genres; `.showheader__prices` "Vanaf € 12,50 per ticket" → price "12,50€"
   (whole euros "10€"). Own productions often have no price (None, ~22%).

## Categories (the production's own Genre field)

- any genre containing "dans"/"hiphop" (Dans, Danstheater, Hiphop) → `dance`
- any other theatre form (Theater, Fysiek/Muziek/Poppen/Circus/Multidisciplinair
  theater, Comedy) → `theater`; both may apply ("Theater, Dans")
- no genre on the page (a few visiting productions) → `theater` (venue default)
- `Leeftijd` N+ with N < 12 → also `kids` (the site's own split is "Families"
  vs "Voor 12+")
- genres are also kept in `annotations` with the age label.

## Exclusions

- Genre containing "Workshop": the weekly "BALLROOM THURSDAYS" (Dans, Workshop
  — a recurring practice night, not a performance).
- Production pages with neither an age nor a genre in their spec block: the
  "OPEN ATELIER" listing (maker only, no price, odd 15:36 start).
- 00:00 placeholder entries for a production that also has timed sessions that
  day (ZEG MAAR DAG 2027-03-28 had two 00:00 rows next to 13:00/16:00).
- Cancelled (`Geannuleerd`) performances.

## Verification

Last verified: 2026-10-14 via HTTP cross-check. Live: 106 events, 2026-10-16
→ 2027-06-13, time 100%, price 78% (incl. 5 sold-out). For 9 productions
(fabrica, lets-flow, samar…, zeg-maar-dag, laqua, pops-of-the-top, berg,
wapens, double-tap-trap) the production page was fetched fresh and its dates
table parsed with throwaway regexes (public, non-school, Maaspodium, upcoming
rows): date/time sets identical to the scraper's; Genre and "Vanaf €" price
match the scraper's categories/prices.
