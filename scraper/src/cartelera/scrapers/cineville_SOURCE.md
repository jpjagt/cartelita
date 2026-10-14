# cineville — source map

Multi-venue **whitelist** source: the Cineville network's public JSON API,
for the Rotterdam + Utrecht arthouse cinemas this source owns per
`docs/nl-cities-plan.md`.

| venue_slug | Cineville venue | city | Cineville UUID |
|---|---|---|---|
| kino-rotterdam | KINO | rotterdam | 57922ba0-1dba-49bc-b893-2be7b8d9ef4d |
| cinerama | Cinerama | rotterdam | 90c6c215-c9b0-4461-987e-edbc096e219a |
| wenneker | Wenneker Cinema (Schiedam) | rotterdam | 8e7736a9-ee16-4f52-9abf-fa1a897af697 |
| louis-hartlooper | Louis Hartlooper Complex | utrecht | fd5a6386-c176-4839-8641-07fac03ca2e2 |
| springhaver | Springhaver | utrecht | c15751d4-4d4b-4cc8-a158-70f2c8fe4cb7 |
| slachtstraat | Slachtstraat | utrecht | ddb268bf-0634-4f5d-b396-e7a5549d2451 |
| de-sien | De Sien | utrecht | 310f9378-52b5-4aaf-b7b6-4b4b1f6fb1bb |

UUIDs come from `GET https://api.cineville.nl/venues?page[limit]=100` (98
venues). **Deliberately not whitelisted:** all Amsterdam cinemas (film there
comes from jazzin), LantarenVenster and WORM (own scrapers, other batches),
and the festival pseudo-venues (Wildlife Film Festival Rotterdam, Nederlands
Film Festival, Queer Film Festival Utrecht, Kaboom — festival accounts, not
cinemas; their screenings take place at the venues above or elsewhere).

## Fetch

`GET https://api.cineville.nl/events?venueId[eq]=<uuid>&startDate[gte]=<today 00:00 Amsterdam, as UTC ISO>&embed[production]=true&page[limit]=200`,
one venue at a time; cursor pagination via `_links.next.href` (`page[after]`,
ordered by createdAt — not by date). Plain httpx, no auth, honest UA
`Cartelita (+https://cartelita.july.dev)`. ~7 requests per run.

## Fields

| field | source |
|---|---|
| title | `productionHint.title` (the venue's own POS title for that screening, e.g. "Vertigo (1958) a 70mm presentation"), whitespace-normalized; fallback `_embedded.production.title`. The production title drops occurrence detail, so the POS title wins. |
| start/end | `startDate` / `endDate` (UTC `Z`) → Europe/Amsterdam local date + time |
| source_url | `ticketingUrl` (per-occurrence ticket page on the venue site). Cinerama's is just its homepage → `https://www.cineville.nl/films/<production.slug>` when a production is linked, else the homepage |
| language | `attributes.subtitles` (ISO codes) → `"NL subs"` / `"EN subs"`, as stated. De Sien instead writes `" \| Eng Subs"` at the end of its POS title: that suffix is stripped from the title and becomes `"EN subs"`. Never inferred from `spokenLanguages`. Cinerama and De Sien leave `subtitles` empty → mostly None |
| price | none in the API (Cineville is a subscription) → `None` |
| description | `production.localizableAttributes.shortDescription` (Dutch) |
| image_url | `production.assets.cover.url`, else `poster.url` |
| annotations | `attributes.tags` (`classic`, `preview`, `special`, `70mm`) |
| category | always `film` (every `productionTypeId` observed is `film`) |
| external_id | event `id` (UUID, one per screening). Stable: identical id sets across two fetches; events created months ago (createdAt 2026-04) keep their id through later updates (updatedAt 2026-10) |

About 15% of events have no linked production (`productionId: null`, no
`_embedded.production`) — e.g. KINO's Hong Kong retrospective, Dune: Part
Three at Cinerama. They are real public screenings: kept, with the POS title,
and no description/image.

## Exclusions (curation)

- `isHidden: true` — events Cineville keeps off its public listing: rentals
  ("Verhuur (2u)"), school screenings ("Schoolvoorstelling"), staff/camera
  sessions, private parties. Side effect: a few hidden items that the venue
  does advertise are missed (2026-10-14: De Sien's "Dolle Mina Filmclub"
  film+talk) — we follow Cineville's flag rather than guess.
- `EXCLUDED_SERIES` in `cineville.py` — named series the venue's OWN site
  classifies as non-screenings (verified 2026-10-14), matched on the POS title:
  - Louis Hartlooper: "De Ins en Outs van Film" (deel N), "Het Verhaal van de
    Documentairemaker", "Van Klassieker tot Pulp", "Film als Filosofie" —
    hartlooper.nl "Genre: Filmcursus" (lecture courses; the list lives at
    hartlooper.nl/over-lhc/filmcursus/ — new courses there need adding).
  - Slachtstraat: "Schrijfcafé" — "een unieke schrijfworkshop".
  - De Sien: "Cinekid Medialab" — day-long interactive media workshop.
  - KINO: "Event" — a bare POS placeholder whose ticket page is empty.
- No venue excluded on quality grounds: all seven are curated arthouse
  cinemas. Cinerama is Kinepolis-operated but programmes arthouse/Cineville
  titles plus a few blockbusters (kept — they're on the venue's agenda).

## Verification

Last verified: 2026-10-14 via HTTP cross-check, independent of the scraper:

- Venue ticket pages (`<title>` "[Tickets] - <title> - <dag> <d mmm>|<HH:MM>")
  for 3 random events each at KINO, LHC, Springhaver, Slachtstraat: titles and
  dates match. Times match in summer time; for dates after 25 Oct the ticket
  page `<title>` reads one hour EARLIER — a bug in that page title: the
  venue's own film pages (hartlooper.nl/films/roter-himmel-2023 "wo 6 jan
  18:45", slachtstraat.nl/films/scream-1996 "za 31 okt 19:00") agree with our
  UTC→Amsterdam conversion. Subtitles agree ("Ondertiteling Nederlands" ↔
  `NL subs`).
- Wenneker homepage agenda: first 6 screenings (title, date, time) match.
- De Sien homepage "Vandaag" list: all 5 listed screenings match.
- Cinerama (cineramabios.nl, Kinepolis; 403 to httpx, OK via curl_cffi
  impersonate): every Cineville screening start (all 309) appears with the
  same UTC instant in its embedded `Drupal.settings` session feed.
- KINO: some ticket pages render client-side; POS titles ("KINO Live: La La
  Land (2016) 10th anniversary", "Dune: Part Three – a 70mm presentation")
  match the kinorotterdam.nl/agenda film list verbatim.

Live run 2026-10-14: 1164 events (KINO 341, Cinerama 309, LHC 212,
Slachtstraat 122, Springhaver 81, De Sien 64, Wenneker 35), 2026-10-14 →
2027-04-07. Time 100%, language 60% (0% at Cinerama/De Sien except the
title-stated EN subs), image/description ~90%, price 0% (none in source).
