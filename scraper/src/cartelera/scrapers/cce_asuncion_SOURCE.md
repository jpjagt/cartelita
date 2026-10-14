# CCE Juan de Salazar (CCE Asunción) — source map

Venue slug: `cce-asuncion` (Asunción) — Centro Cultural de España Juan de
Salazar, Herrera 834. Categories film, theater, kids (whitelisted memberships).

Own site: `https://cceasuncion.aecid.es` — the AECID network's Liferay
platform, read through the shared **`_aecid.py`** (reusable for the other
Centros Culturales de España on `*.aecid.es`: Montevideo, Lima, Guatemala,
Tegucigalpa, Santiago … all expose the same agenda portlet). httpx with the
Cartelita browser UA.

## Data

1. `GET /eventos/buscador-de-eventos` → the agenda container's
   `data-listado-url` (a Liferay resource URL; the portlet instance id differs
   per site) and the parameter namespace `_<p_p_id>_`.
2. `GET <listado-url>&<ns>keywords=&<ns>start=N&<ns>from=<today>&<ns>to=&<ns>sort=asc`
   → JSON `{totalHits, size: 12, documents: [{articleId, title, html}]}`; each
   `html` is a card with the detail link (`a.title` → `/w/<slug>`), image, all
   dates and category labels (`.cat-reco`). Paged by 12 until `totalHits`.
   `from` keeps items with any date ≥ today (their past dates included).
3. Detail page `/w/<slug>` (fetched only for cards with a programme label):
   `.col-izq h1` title, `h2.tit-h4` subtitle, `.col-izq img` image,
   `.col-content` body, and the `.col-der dl` fields — **Categoría** (one `dd`
   per label), **Fecha** (one `.fecha-repetible-item` per date, the "Mostrar
   más" ones included as `.fecha-repetible-oculta`), **Horario** (optional free
   text), **Lugar** (free text).

## Fields

| Field | Source |
|---|---|
| rows | one per (date ≥ today, start time) of the item |
| `start_time` | Horario's first clock time ("19.30 horas." → 19:30, "18.00 a 20.00 horas." → 18:00); without one (or "Según programación."), the times the body states right after that date ("miércoles 28 de octubre, 19:30 horas") — several on one date (31 Oct: 18:00 and 20:00) → several rows; none → no time |
| `title` | h1 (the cycle's/show's title — individual films of a cycle are in the body, not structured) |
| `price` | a guaraní amount in the body (`pyg_price`), else "free" for "acceso/entrada libre", "libre y gratuito"; else None |
| `external_id` | `<articleId>@YYYY-MM-DDTHHMM` |
| `annotations` | non-programme labels (e.g. "Diversidad / Géneros") + the subtitle |
| `description` | body text (≤ 2000 chars) |

## Curation (the agenda's own labels + Lugar)

- Programme: `Cine / Audiovisual` → film, `Escénicas` → theater (the agenda's
  one performing-arts label; it covers dance and clown too — no finer label).
  `Infantil / Juvenil` adds kids to a programme item.
- Vetoed by `Formación` (workshops/courses, e.g. "Arquetipos en el cine",
  "Taller de Crítica de Artes Escénicas") and `Exposiciones`.
- Left out for lack of a programme label: exhibitions (Artes Visuales),
  reading clubs and children's reading (Letras), community/heritage/
  environment items, forums (Cultura para el Desarrollo), month overviews.
- `Música / Sonido` (≈3 items/year: jazz piano, flamenco, a trio) is **not
  mapped**: the label carries no genre and we don't guess from titles.
- **Lugar** must mention "Centro Cultural de España" or "CCE" (or be empty):
  items elsewhere (Sala La Correa, Casa Bicentenario, Auditorio OSN) are
  dropped. Multi-place items ("Cine de Barrio y Centro Cultural de España",
  "ICPA, CCE y Cine Villamorra") are kept whole — Lugar isn't per date, so a
  date at the partner venue can appear under CCE (e.g. 5 Oct 2026 "El
  desencanto" at Cine de Barrio). Known imperfection.

## Verification

Last verified: **2026-10-14 via HTTP cross-check.** Live: 15 listing items
from today → 1 programme item ("Octubre de cine español") → 5 rows,
2026-10-28 → 2026-10-31, all `free`, times 5/5, image 5/5. Independent check:
read the live detail page text — "Miércoles 28 de octubre, 19:30 horas",
"Jueves 29 … 19:30", "Viernes 30 … 19:30", "Sábado 31 de octubre, 18:00 horas"
and "… 20:00 horas", "Acceso libre y gratuito" — identical. The other 14
items: exhibitions, reading clubs, workshops (Formación, incl. "Arquetipos en
el cine"), community/forum items — excluded as above. Cold-start per-day
counts match.
