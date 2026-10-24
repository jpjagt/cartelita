# clusterflick — London's curated cinemas (multi-venue whitelist source)

**Credit:** film listings data from **Clusterflick** (https://clusterflick.com,
GitHub org `clusterflick`, maintainer Alistair Brown). All pipeline repos,
including `clusterflick/data-transformed` whose releases we read, are
**MIT**-licensed; attribution is the licence's condition — keep this credit
here, in the module docstring, and on the site's about/credits. The TMDB
summaries/posters inside the data are TMDB's, not Clusterflick's: **not used**.
Decision record: `docs/london.md`, "Film" + Decision 3.

## Data source

- One GitHub **release asset per venue** in `clusterflick/data-transformed`:
  `https://github.com/clusterflick/data-transformed/releases/latest/download/<asset>`
  (a redirect to objects.githubusercontent.com; no API call, no auth). Plain
  `httpx`, `CARTELITA_UA`, ≤3 concurrent. 20 requests per run.
- Asset = JSON list of items: `title` (the venue's **raw** title), `url` (the
  venue's film page, sometimes an Eventbrite/Eventive/lu.ma page for a
  third-party screening), `category`, `overview`, `themoviedb`,
  `performances[]` (`time` epoch ms UTC, `bookingUrl`, `notes`, `format`,
  `status.soldOut`, `accessibility`, optional `screen`).
- Exact asset names: `GET https://api.github.com/repos/clusterflick/data-transformed/releases/latest`
  → `assets[].name` (477 assets on release `20261024.173639`).
- Release-age guard: the scraper makes that one API call per run (limit 60/h
  unauthenticated) and **fails the source if the latest release is > 3 days
  old** (Clusterflick publishes several a day; older = its pipeline stalled,
  and a stale file would still look "healthy" because it holds future
  screenings). If the API call itself fails/rate-limits, the check is skipped
  with a warning — the assets are the data.

## Whitelist (asset → venue slug)

| Asset | Venue slug |
|---|---|
| `bfi.org.uk-southbank` | `bfi-southbank` |
| `princecharlescinema.com` | `prince-charles-cinema` |
| `thegardencinema.co.uk` | `the-garden-cinema` |
| `riocinema.org.uk` | `rio-cinema` |
| `phoenixcinema.co.uk` | `phoenix-cinema` |
| `thelexicinema.co.uk` | `the-lexi-cinema` |
| `thearzner.com` | `the-arzner` |
| `actonecinema.co.uk` | `actone-cinema` |
| `thecastlecinema.com` | `the-castle-cinema` |
| `closeupfilmcentre.com` | `close-up-film-centre` |
| `ica.art` | `ica` |
| `genesiscinema.co.uk` | `genesis-cinema` |
| `thenickel.co.uk` | `the-nickel` |
| `cinemamuseum.org.uk` | `the-cinema-museum` |
| `curzon.com-soho` | `curzon-soho` |
| `curzon.com-bloomsbury` | `curzon-bloomsbury` |
| `institut-francais.org.uk` | `cine-lumiere` (second wave) |
| `regentstreetcinema.com` | `regent-street-cinema` (second wave) |
| `arthousecrouchend.co.uk` | `arthouse-crouch-end` (second wave) |
| `thehorsehospital.com` | `the-horse-hospital` (second wave) |

Addresses and **explicit lat/lng** come from Clusterflick's venue records
(`data-combined` `combined-data.json` → `venues[<asset>]`.address/geo), so
these venues are never geocoded. (Fixed one typo: Lexi's "Chamberlayne Roadd".)

- **Bertha DocHouse:** no asset or Clusterflick venue of its own — its
  screenings are in `curzon.com-bloomsbury` with the note "Programmed by
  Bertha Dochouse" (73 performances on 2026-10-24). **One venue**
  (`curzon-bloomsbury`); the note becomes an annotation, so DocHouse
  screenings stay identifiable if they ever get their own venue.
- **Second wave, included:** Ciné Lumière (French/world cinema, festivals —
  276 perfs), Regent Street Cinema (repertory, silent + live organ,
  festivals), ArtHouse Crouch End (independent arthouse), The Horse Hospital
  (underground film; its Clusterflick asset is already its own
  `?category=Film` listing).
- **Second wave, excluded: JW3.** A multi-arts Jewish cultural centre whose
  cinema slate is largely first-run/NT Live plus UKJFF; putting it here would
  make clusterflick its owning source and block a future JW3 source for its
  whole programme. Its UKJFF screenings at other venues still come through.
- **Never on the whitelist** (owned by another London source): Barbican, Kiln,
  Rich Mix, Cafe OTO, Cadogan Hall, Conway Hall, EartH, Bush Theatre, Dalston
  Superstore (Clusterflick has assets for some of them). Test-enforced.
- Not included (docs/london-research/film.md §3): multiplexes, Picturehouse,
  Everyman, Electric, Goethe-Institut, Curzon's other sites.

## Field map (one ScrapedEvent per performance)

| Field | Source |
|---|---|
| `title` | item `title`, whitespace-collapsed (venue's raw title, never `themoviedb.title`) |
| `start_date` / `start_time` | performance `time` (epoch ms UTC) → Europe/London |
| `source_url` | item `url` |
| `external_id` | `f"{bookingUrl}@{YYYY-MM-DDTHH:MM}"` — booking URLs are per screening at most venues but per *film* at BFI / Prince Charles / ICA / Ciné Lumière / Arzner, so qualified with the London start time |
| `category_slugs` | `["film"]` |
| `price` | `"sold-out"` when `status.soldOut` is true, else `None` (Clusterflick carries no prices) |
| `annotations` | item category when not `movie` (`shorts`, `multiple-movies`); `format.source` (35mm, 70mm, 16mm, "35mm / DCP", vhs…), `3D`; each line of `notes` ("Sing Along", "Part of <season>", "Programmed by Bertha Dochouse", "+ Q&A"…); accessibility flags → `subtitled`, `audio-described`, `hard-of-hearing`, `baby-friendly`, `relaxed` |
| `description` | **empty in v1** — the only text is TMDB's summary, which needs TMDB attribution |
| `image_url` | **none** — TMDB/venue posters, licensing not clear |
| `language` | `None` (`subtitled` doesn't say which language) |

Performances whose London date is before today are dropped (the release is
hours old). A screening listed under two items (seen at Ciné Lumière: "Le
Plein de Super" twice) is emitted once (first wins, same external_id).

## Curation rule (Clusterflick's own item `category`, never titles)

Kept: `movie`, `multiple-movies`, `shorts`. Dropped (counts across the 20
assets, release 2026-10-24): `talk` (~37), `music` (~17), `event` (~13), `tv`
(6), `quiz` (5), `workshop` (4), `comedy` (2), and any new label (logged at
info).

- **`talk` dropped.** It mixes film talks (BFI "in conversation", UEA Film50)
  with non-film ones (Cinema Museum "Ronnie, Reggie & Me", "Beatles, Bowie &
  Me", "The Bill Reunion"); the label can't tell them apart and titles may
  not be used. Revisit per venue (e.g. keep `talk` at BFI only) if wanted.
- **`tv` dropped.** TV previews/sing-alongs (BFI TV Preview, PCC "Solve Along
  A Murder She Wrote", Arzner Doctor Who) aren't film screenings.
- Note `music` items the venue itself types as "Film" (Rio's "folk + cosmic
  horror rave", "Velcro Flats presents POZI") are dropped — Clusterflick's
  label wins, and it's right.
- Kept as Clusterflick labels them: NT Live broadcasts at ArtHouse
  (`movie`), and third-party screenings Clusterflick attributes to the venue
  from Eventbrite/Eventive/lu.ma (UKJFF, WWIFF, PRIFF, LIAF festival
  screenings, plus some hires/premieres; ~75 items, 1 perf each). They are
  real screenings at the venue but not always on the venue's own site —
  owner may want to restrict to venue-domain URLs + festivals later.

## Health / failure modes

- An asset that 404s / errors / isn't a JSON list → that venue gets no
  events this run (warning logged); the per-venue health rules flag it.
- **More than half the assets failing → the source raises** (broken).
- No screenings at all → raises. Stale release (> 3 days) → raises.
- Clusterflick lags the venues by hours (release cadence), so a screening the
  venue dropped this afternoon is still emitted tonight (seen: two Rio items);
  the missed-runs/hidden mechanism handles removals.
- Bus factor: one maintainer. If it lapses, all London film goes dark at
  once; each venue has a direct fallback (docs/london.md "Film" table).

## Verification (2026-10-24, ~23:00 BST, release `20261024.173639`)

Live run: **3236 events**, 20/20 assets OK; sold-out 133 (4%); price
otherwise None by design (0% priced); 1905 (59%) with annotations.
Per venue: PCC 683, BFI 319, Curzon Bloomsbury 306, Ciné Lumière 274, Garden
205, Lexi 161, ActOne 157, Genesis 151, Curzon Soho 138, ICA 132, Arzner 122,
Rio 106, Nickel 92, Phoenix 88, Castle 84, Close-Up 67, ArtHouse 60, Cinema
Museum 41, Regent Street 37, Horse Hospital 13.

HTTP cross-check against the venues' own sites, with throwaway parsers
independent of the scraper:

- **Prince Charles** (`/whats-on/` HTML, `.jacro-event` → heading date + `.time`
  + `.soldfilm_book_button`), screenings from 25 Oct: 680 on the site vs 683
  ours, **674 identical on (film URL, date, time, sold-out)**; 0 title
  mismatches. The 6 site-only rows are the dropped quiz/tv/talk items; ours-
  only are 3 off-site third-party screenings (TicketSource/Eventbrite) and
  rows of 24 Oct. Format tags agree ("35mm / DCP", "70mm", "Sing Along").
- **Rio** (Savoy `var Events` JSON in `/Rio.dll/WhatsOn`): 103 site
  performances vs 106 ours, 101 identical on (film URL, date, time); titles
  identical except the site JSON's `&amp;` entities (Clusterflick decodes
  them); sold-out flags all agree; booking URLs match the site's performance
  URLs. Site-only: the 2 `music` items (above). Ours-only: 3 Eventbrite
  festival/preview screenings and 2 screenings removed from the site since
  the release.
- Cold start (scratch DB): 3236 rows == scraper output; all `film`; each
  venue on the London `film` list.
