# ICPA – Goethe-Zentrum — source map

Venue slug: `icpa-gz` (Asunción) — Instituto Cultural Paraguayo-Alemán,
Juan de Salazar 310 esq. Artigas. Categories film, classical, dance, theater,
kids (each its own list membership, whitelisted).

Own site: `https://www.icpa-gz.org.py` — WordPress + The Events Calendar.
Data: the Tribe REST API via the shared `_tribe_events.py`
(`/wp-json/tribe/events/v1/events?per_page=50`, today → +2 years, paginated).
Plain httpx with `CARTELITA_BROWSER_HEADERS` works (no curl_cffi needed as of
2026-10-14, despite an earlier report of a 406 to bare curl).

## Fields

| Field | Source |
|---|---|
| `title`, `source_url`, `image_url`, `external_id` | `title` (unescaped), `url`, `image.url`, post `id` (one post per occurrence: multi-session series are separate posts "1/5 … 5/5") |
| `start_date`/`start_time` | `start_date` — site-local (`timezone: America/Asuncion`); `all_day` → no time |
| `price` | `cost_details.values` in guaraníes ("300.000", "40000", "0") → highest → `format_pyg` ("40.000₲", 0 → "free"); else `cost` "Gratuito" → "free". Not `tribe.cost_price` (that one parses euros). |
| `description` | `excerpt` (usually empty) |
| `annotations` | the item's other event categories (e.g. "Música", "Semana Alemana \| Deutsche Woche"), minus neutral ones (Arte, Cultura, Evento presencial, apoyado por el ICPA-GZ) |

## Curation (the calendar's own structure only)

1. **Venue**: the Tribe venue name must contain "Instituto Cultural
   Paraguayo-Alemán" — the main building (venue 435), Salón Rolando Rasmussen
   (6015), Biblioteca Ulrich Schmidl (5315). Partner events elsewhere (Cine
   Villamorra, Colegio Goethe, Teatro Municipal, CCE, Alianza Francesa, Online)
   are dropped: they belong to other venues.
2. **Programme label** required: Cine / Haus-Kino \| Cine / Ciclos de Cine
   Alemán / Ciclo de Cine Europeo en Paraguay → `film`; Concierto →
   `classical`; Danza → `dance`; Teatro → `theater`; plus "Evento para niñas y
   niños" → `kids` on a programme item.
3. **Vetoed** by any of: Taller, Capacitación, Formación profesional, Charla,
   Conferencia, Conversatorio, Exposición, Convocatoria, Concurso, Beca,
   Exámenes internacionales, Estudiar en Alemania, Feria, Feria Al Parque,
   Mercadillo navideño, Evento digital, Goethe on Demand, Presentación,
   Presentación del libro, Deporte.

Left out as a result: workshops/courses (most of the calendar), reading clubs
("Tiempo de lectura"), talks, exhibitions, calls, choir rehearsals/auditions
(Chor without Concierto), and **Música-only** items — album listening
parties, disco nights, "ICPA Treff" socials — which are not concerts.

## Quirks

- "Concierto" is the only concert label; it covers chamber/guitar/choir
  recitals (incl. Suzuki school recitals) and occasionally Paraguayan song.
  Mapped to `classical` as the dominant register — no finer label exists.
- The site's own labels occasionally misfire (2025: a drawing workshop and six
  theatre-audition dates tagged only "Teatro"); we don't title-filter, so such
  items would pass. 2026 labelling has been consistent (workshops always carry
  "Taller").
- Thin: most months have 0–3 programme items; the calendar's volume is
  workshops.

## Verification

Last verified: **2026-10-14 via HTTP cross-check.** Live: 19 upcoming calendar
items → 1 programme event (Concierto "Guitarra Paraguaya", 2026-10-23 20:00,
Salón Rolando Rasmussen, `40.000₲`). Independent check against the public
HTML list view `/eventos/lista/` and the event page (`.tribe-events-schedule`
"octubre 23 @ 20:00 - 21:00 Gs40000", categories "Arte, Concierto, Cultura,
Evento presencial, Música") — agrees. The other 18 are workshops (Taller), a
reading club, a library "merienda", an off-site Colegio Goethe evening and a
Música-only listening party — all excluded by the rules above.
