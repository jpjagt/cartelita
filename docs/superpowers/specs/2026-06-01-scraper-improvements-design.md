# Scraper Improvements & Frontend Day Rollover — Design Spec

Date: 2026-06-01

## Overview

Six improvements to the Cartelera scraper layer and frontend agenda grouping,
ordered so foundational changes (price convention) land before the scrapers that
depend on them.

---

## 1. `free` / `sold-out` price convention

**Convention:** `ScrapedEvent.price` must be one of:
- `None` — price unknown or not applicable
- `"free"` — no admission cost
- `"sold-out"` — tickets exhausted
- A concise display string — informative for the user; prefer a plain value like
  `"10€"` or `"10–22€"`. Skip member-tier and discount prices; show a range only
  when tiers differ meaningfully.

**Per-scraper normalizations:**
| Scraper | Raw value | Normalized |
|---|---|---|
| Big Bang | `"Entrada gratuita"` | `"free"` |
| Jamboree | `"s.o."` | `"sold-out"` |
| Sala Beckett | `"Activitat gratuïta"` | `"free"` |
| Harlem / Robadors / Casa Figari | audit DB for "free"-equivalent strings | `"free"` |

**Frontend:** Translate `"free"` and `"sold-out"` per locale in the price display
component (e.g. `"free"` → `"Gratis"` / `"Gratis"` / `"Free"`; `"sold-out"` →
`"Agotado"` / `"Exhaurit"` / `"Sold out"`).

**Documentation:** Add price convention to `writing-a-scraper` skill.

---

## 2. Sala Beckett: max price extraction

The Sala Beckett `Preu` field contains verbose strings like
`"D'11 € a 22 € Pack Anatomia de Ricard: 28 €"`. We extract the highest numeric
value and emit it as e.g. `"28€"`.

**Logic:**
1. Check for free-admission marker first → emit `"free"`.
2. Otherwise, extract all `\d+` integers from the raw price string.
3. If any found, emit `f"{max_value}€"`.
4. If none found, emit the raw string as-is (fallback).

---

## 3. Sala Beckett Jazz Hour (static emitter with live assertion)

The "Cicle de Jazz — El Menjador de la Beckett" runs every Sunday 12:00–13:00
from September through July (not August).

**Implementation inside `sala_beckett.py`:**
1. Fetch `https://www.salabeckett.cat/es/activitat-resta/cicle-de-jazz-el-menjador-de-la-beckett/` once per scrape run.
2. Assert the page body contains `"desde septiembre hasta julio"` (case-insensitive). If not, raise `ValueError("Sala Beckett Jazz cicle assumption changed — check season dates")`.
3. Generate events for the next `LOOKAHEAD_DAYS` days (same constant as Big Bang: 14). For each day in range where `date.weekday() == 6` (Sunday) and `date.month != 8`, emit a `ScrapedEvent`:
   - `title`: `"Cicle de Jazz — El Menjador de la Beckett"`
   - `start_time`: `dt.time(12, 0)`, `end_time`: `dt.time(13, 0)`
   - `category_slugs`: `["jazz"]`
   - `source_url`: the cicle page URL
   - `price`: `"free"` (the page says "Activitat gratuïta")
   - `external_id`: `f"sala-beckett-jazz-menjador-{date.isoformat()}"`
4. These jazz events are merged into `SalaBeckettScraper.scrape()` alongside the theater card events.

---

## 4. Jamboree recurrence bug fix

**Current bug:** `recurrence_hint = "every Monday"` is set whenever `"jam session"` appears anywhere in the title. This fires on one-off "late show & jam session" events that are not on Mondays.

**Fix:** Set `recurrence_hint = "every Monday"` only when BOTH:
- The title is exactly `"Jamboree Jam Session"` (case-insensitive), AND
- `start_date.weekday() == 0` (is a Monday)

Additionally, during the `_enrich` step, if the canonical (`ca`) description
contains `"cada dilluns"` (case-insensitive), also set `recurrence_hint = "every Monday"` regardless of title.

This is evaluated after enrichment (when we have the description), so the
`recurrence_hint` may be updated from `None` → `"every Monday"` in `_enrich`.

---

## 5. Big Bang DJ Sessions: real midnight time

**Current state:** DJ Sessions use `start_time=None` (the all-day sentinel, per
a comment in the scraper). But 00:00 is their actual start time, and `None`
means "time unknown".

**Fix:** Change DJ session rows in `_WEEKLY` from `hour=None, minute=None` to
`hour=0, minute=0`. They will have `start_time=dt.time(0, 0)`.

This means the DB gets real midnight times, and the 05:00 rollover (item 6) will
correctly place them under the previous day's heading.

---

## 6. Frontend 05:00 day rollover

**Change to `groupEventsByDay` in `web/src/lib/agenda.ts`:**

Events with `startTime` in `"00:00"–"04:59"` belong to the **previous calendar
day** (the night that started the evening before). The displayed date heading is
the previous day.

**Logic:**
```typescript
function logicalDate(startDate: string, startTime: string | null): string {
  if (startTime && startTime < "05:00") {
    // Treat as late night of the previous day
    const d = new Date(startDate + "T00:00:00");
    d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0, 10);
  }
  return startDate;
}
```

`groupEventsByDay` uses `logicalDate(ev.startDate, ev.startTime)` as the bucket
key instead of `ev.startDate` directly. The displayed date header = logical date.

**Sort order within a day:** After grouping, within each bucket events are sorted
by a normalized sort key where `null` sorts first, then times ≥ `"05:00"` in
ascending order, then times < `"05:00"` (midnight/post-midnight) last. This
ensures a 00:30 DJ session sorts after the 23:00 jazz concert in the same
logical-night bucket.

---

## 7. Venue data colocation + auto-registration

**New `VenueDefinition` Pydantic model in `scraper/src/cartelera/types.py`:**
```python
class ListMembership(BaseModel):
    list_slug: str
    whitelist_category_slug: str | None = None

class VenueDefinition(BaseModel):
    slug: str
    name: str
    city_slug: str
    address: str | None = None
    site_url: str | None = None
    category_slugs: list[str] = []
    list_memberships: list[ListMembership] = []
```

**`register()` in `scrapers/__init__.py`** gains `venue: VenueDefinition` kwarg:
```python
def register(scraper: Scraper, venue: VenueDefinition) -> None:
    REGISTRY[scraper.venue_slug] = (scraper, venue)
```

`REGISTRY` type changes to `dict[str, tuple[Scraper, VenueDefinition]]`.

**Each scraper** calls `register(scraper=MyScraper(), venue=VenueDefinition(...))` at module bottom.

**`seed.py`** becomes a thin loop:
```python
def seed(session: Session) -> None:
    for scraper, venue_def in REGISTRY.values():
        _upsert_venue_from_definition(session, venue_def)
    session.commit()
```
The per-venue blocks in seed.py are deleted. City and Category rows are still
seeded (they don't belong to any single scraper). `_upsert_venue_from_definition`
replaces the three helpers `_get_or_create_venue`, `_get_or_create_list`,
`_ensure_membership`.

**`run.py`**: when `cmd == "run"`, call `seed_db(session)` automatically before
running scrapers. Since seed is idempotent, this is safe and makes `cartelera seed`
optional for new venue additions.

---

## Implementation Order

1. Price convention (`free`/`sold-out`) + scraper audit
2. Sala Beckett max price
3. Sala Beckett Jazz Hour emitter
4. Jamboree recurrence fix
5. Big Bang DJ midnight time fix
6. Frontend 05:00 rollover (`groupEventsByDay`)
7. Venue colocation + auto-registration refactor
