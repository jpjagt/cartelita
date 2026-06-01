# Scraper Improvements & Frontend Day Rollover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix price display, add Sala Beckett Jazz Hour, fix Jamboree recurrence, make Big Bang DJ sessions show under the correct night, and refactor venue data into scrapers.

**Architecture:** Seven sequential tasks — price convention first (other tasks depend on it), then per-scraper fixes, then the frontend grouping change, finally the venue colocation refactor. All Python changes are TDD against fixtures; the frontend change is tested via unit test of the `groupEventsByDay` function.

**Tech Stack:** Python (scrapers), pytest, httpx, BeautifulSoup, Pydantic (new dep for VenueDefinition), TypeScript/Astro (frontend), Vitest or inline type-checks.

---

## File Map

| File | Change |
|---|---|
| `scraper/src/cartelera/types.py` | Add price docstring convention + `VenueDefinition`/`ListMembership` Pydantic models |
| `scraper/src/cartelera/scrapers/__init__.py` | `register()` gains `venue` kwarg; `REGISTRY` type change |
| `scraper/src/cartelera/scrapers/big_bang.py` | DJ sessions → `dt.time(0, 0)`; `price="free"` |
| `scraper/src/cartelera/scrapers/sala_beckett.py` | Max-price extraction + Jazz Hour static emitter |
| `scraper/src/cartelera/scrapers/jamboree.py` | Recurrence rule tightened |
| `scraper/src/cartelera/scrapers/harlem_jazz_club.py` | `"Entrada libre"` → `"free"` |
| `scraper/src/cartelera/scrapers/robadors.py` | `price="free"` already done (price==0 path); normalise "0€" guard |
| `scraper/src/cartelera/scrapers/casa_figari.py` | `"entrada libre"` → `"free"` |
| `scraper/src/cartelera/seed.py` | Becomes thin loop over `REGISTRY`; venue blocks deleted |
| `scraper/src/cartelera/run.py` | Auto-call `seed_db()` before `run` |
| `scraper/pyproject.toml` | Add `pydantic>=2.0` dependency |
| `web/src/lib/agenda.ts` | `groupEventsByDay` with 05:00 rollover + within-bucket sort |
| `web/src/i18n/index.ts` | Add `price` translations for `"free"` and `"sold-out"` |
| `web/src/components/EventRow.astro` | Translate price before display |
| `scraper/tests/test_big_bang.py` | Update DJ session time assertion |
| `scraper/tests/test_sala_beckett.py` | Update price tests + Jazz Hour tests |
| `scraper/tests/test_jamboree.py` | Update recurrence test |
| `scraper/tests/test_seed.py` | Update for new REGISTRY-driven seed |
| `.claude/skills/writing-a-scraper` | Add price convention section |

---

## Task 1: Price convention — `types.py` docstring + `free`/`sold-out` in Big Bang & Robadors

**Files:**
- Modify: `scraper/src/cartelera/types.py`
- Modify: `scraper/src/cartelera/scrapers/big_bang.py`
- Modify: `scraper/src/cartelera/scrapers/robadors.py`
- Modify: `scraper/tests/test_big_bang.py`

- [ ] **Step 1: Update price docstring in `ScrapedEvent`**

In `scraper/src/cartelera/types.py`, update the `price` field comment in `ScrapedEvent`:

```python
# Price convention: None = unknown, "free" = no admission cost,
# "sold-out" = tickets exhausted, otherwise a concise display string
# (e.g. "10€", "10–22€"). Skip member/discount tiers; show a range
# only when tiers differ meaningfully.
price: str | None = None
```

- [ ] **Step 2: Update Big Bang price to `"free"`**

In `scraper/src/cartelera/scrapers/big_bang.py`, change the price value in `generate_events()`:

```python
price="free",
```

(Was `"Entrada gratuita"`)

- [ ] **Step 3: Update the Big Bang test**

In `scraper/tests/test_big_bang.py`, update `test_all_events_are_free`:

```python
def test_all_events_are_free():
    for ev in _events():
        assert ev.price == "free"
```

- [ ] **Step 4: Run the Big Bang tests**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest tests/test_big_bang.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Verify Robadors already emits `"free"` for price==0**

In `scraper/src/cartelera/scrapers/robadors.py`, the existing code already does:
```python
elif raw_price == "0":
    price = "free"
```
This is correct — no change needed. Confirm by reading lines 148–155.

- [ ] **Step 6: Commit**

```bash
cd /Users/jeroen/code/jpjagt/cartelera && git add scraper/src/cartelera/types.py scraper/src/cartelera/scrapers/big_bang.py scraper/tests/test_big_bang.py
git commit -m "feat: price convention — free/sold-out keywords; update Big Bang"
```

---

## Task 2: Normalize `"free"` in Harlem Jazz Club and Casa Figari

**Files:**
- Modify: `scraper/src/cartelera/scrapers/harlem_jazz_club.py`
- Modify: `scraper/src/cartelera/scrapers/casa_figari.py`

- [ ] **Step 1: Write a failing test for Harlem free price**

In `scraper/tests/test_harlem_jazz_club.py`, add:

```python
def test_free_entry_events_use_free_keyword():
    events = parse_agenda(FIXTURE.read_text())
    free_events = [e for e in events if e.price == "free"]
    # The fixture contains events with "entrada libre" or similar; they must normalize.
    raw_html = FIXTURE.read_text()
    has_libre = "libre" in raw_html.lower() or "gratu" in raw_html.lower()
    if has_libre:
        assert free_events, "expected at least one 'free' priced event"
    # No event should have raw "Entrada libre" or "entrada libre" as price.
    assert not any(
        e.price and "libre" in e.price.lower() for e in events
    ), "raw 'entrada libre' string must be normalized to 'free'"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest tests/test_harlem_jazz_club.py::test_free_entry_events_use_free_keyword -v
```

Expected: FAIL — `"Entrada libre"` is still the raw value.

- [ ] **Step 3: Fix Harlem price normalization**

In `scraper/src/cartelera/scrapers/harlem_jazz_club.py`, in `_parse_title()`, change:

```python
    free = _FREE.search(raw)
    if free:
        price = "Entrada libre"
        raw = raw[: free.start()] + raw[free.end():]
```

to:

```python
    free = _FREE.search(raw)
    if free:
        price = "free"
        raw = raw[: free.start()] + raw[free.end():]
```

- [ ] **Step 4: Write a failing test for Casa Figari free price**

In `scraper/tests/test_casa_figari.py`, add:

```python
def test_free_entry_normalized():
    from cartelera.scrapers.casa_figari import parse_schedule
    image_bytes = (FIXTURES / "casa_figari_schedule.png").read_bytes()
    events = parse_schedule(image_bytes)
    # No event should have raw "entrada libre" as price string.
    assert not any(
        e.price and "libre" in e.price.lower() for e in events
    ), "raw 'entrada libre' must be normalized to 'free'"
```

- [ ] **Step 5: Run test to verify it fails**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest tests/test_casa_figari.py::test_free_entry_normalized -v
```

Expected: FAIL.

- [ ] **Step 6: Fix Casa Figari price normalization**

In `scraper/src/cartelera/scrapers/casa_figari.py`, in `_extract_price()`:

```python
def _extract_price(left_text: str) -> str | None:
    m = _PRICE_RE.search(left_text)
    if not m:
        return None
    raw = m.group(1).strip()
    if "€" in raw:
        return raw
    # "entrada libre" or similar → normalize to canonical keyword
    return "free"
```

- [ ] **Step 7: Run all price tests**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest tests/test_harlem_jazz_club.py tests/test_casa_figari.py -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
cd /Users/jeroen/code/jpjagt/cartelera && git add scraper/src/cartelera/scrapers/harlem_jazz_club.py scraper/src/cartelera/scrapers/casa_figari.py scraper/tests/test_harlem_jazz_club.py scraper/tests/test_casa_figari.py
git commit -m "feat: normalize free-entry prices to 'free' in Harlem and Casa Figari"
```

---

## Task 3: Sala Beckett — max price extraction + `"free"` normalization

**Files:**
- Modify: `scraper/src/cartelera/scrapers/sala_beckett.py`
- Modify: `scraper/tests/test_sala_beckett.py`

- [ ] **Step 1: Write failing tests for new price behaviour**

In `scraper/tests/test_sala_beckett.py`, **replace** the existing `test_price_is_free_text_not_parsed` and `test_most_events_have_a_price` tests with:

```python
def test_most_events_have_a_price():
    events = _all()
    with_price = [e for e in events if e.price]
    assert len(with_price) >= len(events) * 0.85


def test_free_events_use_free_keyword():
    # "Activitat gratuïta" must normalize to "free".
    free = [e for e in _all() if e.price == "free"]
    assert free, "expected free events from the fixture"


def test_price_is_concise():
    # No event should carry the raw verbose price string; we extract max or normalize.
    priced = [e for e in _all() if e.price and e.price != "free"]
    for ev in priced:
        # Should be short: e.g. "22€", "28€", "10€", "8€"
        assert len(ev.price) <= 10, f"price too verbose: {ev.price!r}"
        assert "Personatges" not in ev.price
        assert "Promoció" not in ev.price


def test_price_max_extracted_correctly():
    # "D'11 € a 22 € Pack Anatomia de Ricard: 28 €" → "28€"
    from cartelera.scrapers.sala_beckett import _parse_price
    assert _parse_price("D'11 € a 22 € Pack Anatomia de Ricard: 28 €") == "28€"
    assert _parse_price("D'11 € a 22 €") == "22€"
    assert _parse_price("10 € | Personatges de la Beckett 8 €") == "10€"
    assert _parse_price("Activitat gratuïta") == "free"
    assert _parse_price("Preu: 10€ | Personatges de la Beckett 8€") == "10€"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest tests/test_sala_beckett.py::test_free_events_use_free_keyword tests/test_sala_beckett.py::test_price_is_concise tests/test_sala_beckett.py::test_price_max_extracted_correctly -v
```

Expected: FAIL — `_parse_price` doesn't exist yet.

- [ ] **Step 3: Add `_parse_price` to `sala_beckett.py`**

Add this function after the existing regex definitions (after `_TIME` on line ~41):

```python
_FREE_MARKERS = re.compile(r"gratui?t[a-z]*", re.IGNORECASE)
_PRICE_NUM = re.compile(r"(\d+)\s*€")


def _parse_price(raw: str | None) -> str | None:
    if not raw:
        return None
    if _FREE_MARKERS.search(raw):
        return "free"
    nums = [int(m.group(1)) for m in _PRICE_NUM.finditer(raw)]
    if nums:
        return f"{max(nums)}€"
    return None
```

- [ ] **Step 4: Wire `_parse_price` into `_parse_cards`**

In `_parse_cards`, replace:

```python
        price = _card_field(card, "Preu")
```

with:

```python
        price = _parse_price(_card_field(card, "Preu"))
```

- [ ] **Step 5: Run Sala Beckett tests**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest tests/test_sala_beckett.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/jeroen/code/jpjagt/cartelera && git add scraper/src/cartelera/scrapers/sala_beckett.py scraper/tests/test_sala_beckett.py
git commit -m "feat: Sala Beckett — extract max price, normalize free to 'free'"
```

---

## Task 4: Sala Beckett Jazz Hour static emitter

**Files:**
- Modify: `scraper/src/cartelera/scrapers/sala_beckett.py`
- Modify: `scraper/tests/test_sala_beckett.py`

- [ ] **Step 1: Write failing tests for Jazz Hour**

Add to `scraper/tests/test_sala_beckett.py`:

```python
import pytest
from unittest.mock import patch

JAZZ_CICLE_URL = "https://www.salabeckett.cat/es/activitat-resta/cicle-de-jazz-el-menjador-de-la-beckett/"

def test_jazz_hour_generates_sundays_in_season():
    from cartelera.scrapers.sala_beckett import generate_jazz_hour_events
    today = dt.date(2026, 6, 1)  # Monday
    events = generate_jazz_hour_events(today=today)
    assert events, "expected at least one Sunday in the 14-day window"
    for ev in events:
        assert ev.start_date.weekday() == 6, "must be Sunday"
        assert ev.start_date.month != 8, "must not be in August"
        assert ev.start_time == dt.time(12, 0)
        assert ev.end_time == dt.time(13, 0)
        assert ev.category_slugs == ["jazz"]
        assert ev.price == "free"
        assert ev.source_url == JAZZ_CICLE_URL
        assert ev.external_id == f"sala-beckett-jazz-menjador-{ev.start_date.isoformat()}"


def test_jazz_hour_skips_august():
    from cartelera.scrapers.sala_beckett import generate_jazz_hour_events
    today = dt.date(2026, 7, 28)  # 4 days before August
    events = generate_jazz_hour_events(today=today)
    # No Sundays in August should appear
    assert all(ev.start_date.month != 8 for ev in events)


def test_jazz_hour_raises_on_changed_assumption():
    from cartelera.scrapers.sala_beckett import assert_jazz_cicle_season
    with pytest.raises(ValueError, match="assumption changed"):
        assert_jazz_cicle_season("This page no longer mentions the season.")


def test_jazz_hour_passes_with_valid_page():
    from cartelera.scrapers.sala_beckett import assert_jazz_cicle_season
    # Should not raise when the expected phrase is present.
    assert_jazz_cicle_season("El cicle s'ofereix desde septiembre hasta julio cada any.")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest tests/test_sala_beckett.py::test_jazz_hour_generates_sundays_in_season tests/test_sala_beckett.py::test_jazz_hour_skips_august tests/test_sala_beckett.py::test_jazz_hour_raises_on_changed_assumption tests/test_sala_beckett.py::test_jazz_hour_passes_with_valid_page -v
```

Expected: FAIL — functions don't exist yet.

- [ ] **Step 3: Add constants and Jazz Hour helpers to `sala_beckett.py`**

Add near the top constants block (after `VENUE_SLUG`):

```python
JAZZ_CICLE_URL = "https://www.salabeckett.cat/es/activitat-resta/cicle-de-jazz-el-menjador-de-la-beckett/"
LOOKAHEAD_DAYS = 14
```

Add these functions after `_parse_price`:

```python
def assert_jazz_cicle_season(html: str) -> None:
    """Raise if the Jazz cicle page no longer states the expected season."""
    if "desde septiembre hasta julio" not in html.lower():
        raise ValueError(
            "Sala Beckett Jazz cicle assumption changed — check season dates at "
            f"{JAZZ_CICLE_URL}"
        )


def generate_jazz_hour_events(today: dt.date | None = None) -> list[ScrapedEvent]:
    """Emit Sunday Jazz Hour events for the next LOOKAHEAD_DAYS days (skipping August)."""
    if today is None:
        today = dt.date.today()
    events: list[ScrapedEvent] = []
    for offset in range(LOOKAHEAD_DAYS):
        date = today + dt.timedelta(days=offset)
        if date.weekday() != 6 or date.month == 8:
            continue
        events.append(
            ScrapedEvent(
                title="Cicle de Jazz — El Menjador de la Beckett",
                start_date=date,
                start_time=dt.time(12, 0),
                end_time=dt.time(13, 0),
                source_url=JAZZ_CICLE_URL,
                category_slugs=["jazz"],
                price="free",
                external_id=f"sala-beckett-jazz-menjador-{date.isoformat()}",
            )
        )
    return events
```

- [ ] **Step 4: Wire into `SalaBeckettScraper.scrape()`**

Replace the `scrape()` method:

```python
    def scrape(self) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        seen: set[str] = set()
        for url in LIST_URLS:
            html = httpx.get(url, follow_redirects=True, timeout=30).text
            for ev in parse_agenda(html):
                if ev.source_url in seen:
                    continue
                seen.add(ev.source_url)
                events.append(ev)
        # Jazz Hour: fetch cicle page to assert assumption, then emit static events.
        cicle_html = httpx.get(JAZZ_CICLE_URL, follow_redirects=True, timeout=30).text
        assert_jazz_cicle_season(cicle_html)
        events.extend(generate_jazz_hour_events())
        return events
```

- [ ] **Step 5: Run Sala Beckett tests**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest tests/test_sala_beckett.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/jeroen/code/jpjagt/cartelera && git add scraper/src/cartelera/scrapers/sala_beckett.py scraper/tests/test_sala_beckett.py
git commit -m "feat: Sala Beckett Jazz Hour — Sunday emitter with live season assertion"
```

---

## Task 5: Jamboree recurrence fix + Jamboree `"sold-out"` normalization

**Files:**
- Modify: `scraper/src/cartelera/scrapers/jamboree.py`
- Modify: `scraper/tests/test_jamboree.py`

- [ ] **Step 1: Write failing test for the tightened recurrence rule**

In `scraper/tests/test_jamboree.py`, add:

```python
def test_recurrence_only_on_jam_session_mondays():
    events = _events()
    # Any event with recurrence_hint must be titled "Jamboree Jam Session"
    # and fall on a Monday.
    for ev in events:
        if ev.recurrence_hint is not None:
            assert ev.title.lower() == "jamboree jam session", (
                f"unexpected recurrence_hint on non-Jam-Session event: {ev.title!r}"
            )
            assert ev.start_date.weekday() == 0, (
                f"recurrence_hint set on non-Monday: {ev.start_date} ({ev.title!r})"
            )


def test_non_monday_jam_events_have_no_recurrence():
    events = _events()
    # Events with "jam session" in title that are NOT on Monday must have no hint.
    non_monday_jams = [
        e for e in events
        if "jam session" in e.title.lower() and e.start_date.weekday() != 0
    ]
    for ev in non_monday_jams:
        assert ev.recurrence_hint is None, (
            f"non-Monday jam session got recurrence_hint: {ev.title!r} on {ev.start_date}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest tests/test_jamboree.py::test_recurrence_only_on_jam_session_mondays tests/test_jamboree.py::test_non_monday_jam_events_have_no_recurrence -v
```

Expected: FAIL — the current rule fires on any "jam session" title regardless of day.

- [ ] **Step 3: Fix recurrence rule in `parse_agenda`**

In `scraper/src/cartelera/scrapers/jamboree.py`, in `parse_agenda()`, replace:

```python
        recurrence_hint = "every Monday" if "jam session" in title.lower() else None
```

with:

```python
        recurrence_hint = (
            "every Monday"
            if title.lower() == "jamboree jam session" and start_date.weekday() == 0
            else None
        )
```

- [ ] **Step 4: Add description-based recurrence in `_enrich`**

In `scraper/src/cartelera/scrapers/jamboree.py`, in `_enrich()`, after setting `event.description`:

```python
    if "ca" in parsed:
        _, ca_desc, ca_times = parsed["ca"]
        event.description = ca_desc
        if ca_times:
            event.start_times = ca_times
            event.start_time = min(ca_times)
        # Description-based recurrence: "Cada dilluns" confirms weekly Monday pattern.
        if ca_desc and "cada dilluns" in ca_desc.lower():
            event.recurrence_hint = "every Monday"
```

- [ ] **Step 5: Normalize Jamboree sold-out**

In `scraper/src/cartelera/scrapers/jamboree.py`, in `parse_agenda()`, replace:

```python
        elif "sold out" in article.get_text(" ", strip=True).lower():
            price = "s.o."
```

with:

```python
        elif "sold out" in article.get_text(" ", strip=True).lower():
            price = "sold-out"
```

- [ ] **Step 6: Update the existing jam session test**

In `scraper/tests/test_jamboree.py`, update `test_jam_session_present_with_time_and_recurrence` to match the tighter condition. The fixture's Jam Session event must be a Monday for the test to pass; check the fixture's date. The test currently asserts `j.recurrence_hint == "every Monday"` — this remains valid if the fixture event is a Monday and titled "Jamboree Jam Session". If not, the recurrence may now come from description enrichment (live fetch) which isn't tested here. Update to:

```python
def test_jam_session_present_with_time_and_recurrence():
    events = _events()
    jams = [e for e in events if "jam session" in e.title.lower()]
    assert jams, "expected a Jam Session in the fixture"
    j = jams[0]
    assert j.start_time is not None
    assert j.category_slugs == ["jazz"]
    # Recurrence hint is set only for Monday Jamboree Jam Session events.
    # If the fixture event is on a Monday with title "Jamboree Jam Session", hint is set.
    if j.title.lower() == "jamboree jam session" and j.start_date.weekday() == 0:
        assert j.recurrence_hint == "every Monday"
    else:
        # Non-Monday jam sessions and one-offs must have no hint.
        assert j.recurrence_hint is None
```

- [ ] **Step 7: Run all Jamboree tests**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest tests/test_jamboree.py -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
cd /Users/jeroen/code/jpjagt/cartelera && git add scraper/src/cartelera/scrapers/jamboree.py scraper/tests/test_jamboree.py
git commit -m "fix: Jamboree recurrence only on Monday Jam Sessions; sold-out keyword"
```

---

## Task 6: Big Bang DJ Sessions — real midnight time + frontend 05:00 rollover

**Files:**
- Modify: `scraper/src/cartelera/scrapers/big_bang.py`
- Modify: `scraper/tests/test_big_bang.py`
- Modify: `web/src/lib/agenda.ts`
- Modify: `web/src/i18n/index.ts`
- Modify: `web/src/components/EventRow.astro`

- [ ] **Step 1: Write failing test for DJ midnight time**

In `scraper/tests/test_big_bang.py`, replace `test_dj_sessions_have_no_start_time` with:

```python
def test_dj_sessions_have_midnight_start_time():
    dj_events = [e for e in _events() if e.title == "Dj Session"]
    assert dj_events, "expected Dj Session events"
    for ev in dj_events:
        assert ev.start_time == dt.time(0, 0), (
            f"DJ session on {ev.start_date} must have start_time=00:00, got {ev.start_time}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest tests/test_big_bang.py::test_dj_sessions_have_midnight_start_time -v
```

Expected: FAIL.

- [ ] **Step 3: Update Big Bang DJ session rows**

In `scraper/src/cartelera/scrapers/big_bang.py`, change the two DJ Session entries in `_WEEKLY`:

```python
    (4, "Dj Session",           0,    0,  ["club"],      []),
    ...
    (5, "Dj Session",           0,    0,  ["club"],      []),
```

(Was `None, None`)

Also update the guard in `generate_events()` — `start_time = dt.time(hour, minute) if hour is not None else None` — since hour is now always set, this still works correctly with `hour=0`.

- [ ] **Step 4: Run Big Bang tests**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest tests/test_big_bang.py -v
```

Expected: all pass.

- [ ] **Step 5: Update `groupEventsByDay` in `web/src/lib/agenda.ts`**

Replace the entire file with:

```typescript
import type { AgendaEvent, AgendaDay } from "@/lib/types";

/** Events 00:00–04:59 belong to the previous calendar day (late night of that evening). */
function logicalDate(startDate: string, startTime: string | null): string {
  if (startTime && startTime < "05:00") {
    const d = new Date(startDate + "T00:00:00");
    d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0, 10);
  }
  return startDate;
}

/** Sort key: null first, then times ≥ 05:00 ascending, then times < 05:00 (post-midnight) last. */
function timeSortKey(t: string | null): string {
  if (t === null) return "0";
  if (t >= "05:00") return "1" + t;
  return "2" + t;  // 00:xx–04:xx sort after normal evening times
}

/** Group a chronologically-sorted event list into per-day buckets using 05:00 as the day boundary. */
export function groupEventsByDay(events: AgendaEvent[]): AgendaDay[] {
  const buckets = new Map<string, AgendaEvent[]>();
  for (const ev of events) {
    const date = logicalDate(ev.startDate, ev.startTime);
    if (!buckets.has(date)) buckets.set(date, []);
    buckets.get(date)!.push(ev);
  }
  // Sort bucket keys (dates) ascending, then sort events within each bucket.
  const days: AgendaDay[] = [];
  for (const date of [...buckets.keys()].sort()) {
    const evs = buckets.get(date)!;
    evs.sort((a, b) => timeSortKey(a.startTime).localeCompare(timeSortKey(b.startTime)));
    days.push({ date, events: evs });
  }
  return days;
}
```

- [ ] **Step 6: Add price translations to i18n**

In `web/src/i18n/index.ts`, add a `prices` field to the `Strings` interface and populate it:

```typescript
interface Strings {
  siteTitle: string;
  noEvents: string;
  back: string;
  categories: Record<string, string>;
  prices: Record<string, string>;
}
```

And in `DICT`:
```typescript
  ca: {
    ...
    prices: { free: "Gratuït", "sold-out": "Exhaurit" },
  },
  es: {
    ...
    prices: { free: "Gratis", "sold-out": "Agotado" },
  },
  en: {
    ...
    prices: { free: "Free", "sold-out": "Sold out" },
  },
```

- [ ] **Step 7: Translate price in `EventRow.astro`**

In `web/src/components/EventRow.astro`, add a `locale` prop and translate price:

```astro
---
import type { AgendaEvent, Locale } from "@/lib/types";
import { t } from "@/i18n";
interface Props { event: AgendaEvent; locale: Locale }
const { event, locale } = Astro.props;
const strings = t(locale);
const displayPrice = event.price
  ? (strings.prices[event.price] ?? event.price)
  : "";
---
<tr>
  <td class="time">{event.startTime ?? ""}</td>
  <td class="title">
    <a href={event.sourceUrl} target="_blank" rel="noopener">{event.title}</a>
    {event.recurrenceHint && <span class="recurs" title={event.recurrenceHint}>↻</span>}
  </td>
  <td class="venue">{event.venueName}</td>
  <td class="price">{displayPrice}</td>
</tr>
<style>
  td { padding: 0.4rem 0.75rem; border-bottom: 1px solid #eee; vertical-align: top; }
  .time { white-space: nowrap; color: #444; }
  .recurs { color: #888; margin-left: 0.3rem; cursor: help; }
  .price { white-space: nowrap; color: #444; }
  a { color: inherit; text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
```

- [ ] **Step 8: Update `AgendaDay.astro` to pass locale to EventRow**

`AgendaDay.astro` already accepts `locale` in its Props. Update just the `EventRow` invocation to forward it:

```astro
    <tbody>{day.events.map((e) => <EventRow event={e} locale={locale} />)}</tbody>
```

- [ ] **Step 10: Commit**

```bash
cd /Users/jeroen/code/jpjagt/cartelera && git add scraper/src/cartelera/scrapers/big_bang.py scraper/tests/test_big_bang.py web/src/lib/agenda.ts web/src/i18n/index.ts web/src/components/EventRow.astro web/src/components/AgendaDay.astro
git commit -m "feat: DJ sessions use midnight time; 05:00 day rollover; localized free/sold-out"
```

---

## Task 7: Venue data colocation + auto-registration

**Files:**
- Modify: `scraper/src/cartelera/types.py`
- Modify: `scraper/src/cartelera/scrapers/__init__.py`
- Modify: `scraper/src/cartelera/scrapers/big_bang.py`
- Modify: `scraper/src/cartelera/scrapers/casa_figari.py`
- Modify: `scraper/src/cartelera/scrapers/harlem_jazz_club.py`
- Modify: `scraper/src/cartelera/scrapers/jamboree.py`
- Modify: `scraper/src/cartelera/scrapers/robadors.py`
- Modify: `scraper/src/cartelera/scrapers/sala_beckett.py`
- Modify: `scraper/src/cartelera/seed.py`
- Modify: `scraper/src/cartelera/run.py`
- Modify: `scraper/pyproject.toml`
- Modify: `scraper/tests/test_seed.py`

- [ ] **Step 1: Add pydantic to dependencies**

In `scraper/pyproject.toml`, add `"pydantic>=2.0"` to `dependencies`:

```toml
dependencies = [
    "sqlalchemy>=2.0",
    "psycopg[binary]>=3.2",
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
    "pillow>=12.2.0",
    "pydantic>=2.0",
    ...
]
```

Then run:
```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv sync
```

- [ ] **Step 2: Add `VenueDefinition` and `ListMembership` to `types.py`**

In `scraper/src/cartelera/types.py`, add at the top:

```python
from pydantic import BaseModel
```

Then add after the existing dataclasses:

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

- [ ] **Step 3: Update `register()` and `REGISTRY` in `scrapers/__init__.py`**

Replace the contents of `scraper/src/cartelera/scrapers/__init__.py` with:

```python
from cartelera.scrapers.base import Scraper
from cartelera.types import VenueDefinition

# Maps venue_slug -> (Scraper instance, VenueDefinition).
REGISTRY: dict[str, tuple[Scraper, VenueDefinition]] = {}


def register(scraper: Scraper, venue: VenueDefinition) -> None:
    REGISTRY[scraper.venue_slug] = (scraper, venue)
```

- [ ] **Step 4: Update `run.py` to unpack REGISTRY tuples**

In `scraper/src/cartelera/run.py`, update the two places that use `REGISTRY`:

```python
def run_one(session: Session, venue_slug: str) -> ScrapeResult:
    scraper, _ = REGISTRY[venue_slug]
    ...

def run_all(session: Session) -> list[ScrapeResult]:
    return [run_one(session, slug) for slug in REGISTRY]
```

Also in `main()`, auto-seed before run:

```python
        # cmd == "run"
        seed_db(session)
        target = args[1] if len(args) > 1 else "all"
        ...
```

- [ ] **Step 5: Update each scraper's `register()` call**

For each scraper, add a `VenueDefinition` import and update the `register()` call at the bottom. Here are all six:

**`jamboree.py`** — replace `register(JamboreeScraper())` with:
```python
from cartelera.types import VenueDefinition, ListMembership

register(
    scraper=JamboreeScraper(),
    venue=VenueDefinition(
        slug="jamboree",
        name="Jamboree",
        city_slug="barcelona",
        address="Plaça Reial, 17, 08002 Barcelona",
        site_url="https://jamboreejazz.com",
        category_slugs=["jazz", "club"],
        list_memberships=[
            ListMembership(list_slug="jazz", whitelist_category_slug="jazz"),
            ListMembership(list_slug="club", whitelist_category_slug="club"),
        ],
    ),
)
```

**`harlem_jazz_club.py`** — replace `register(HarlemJazzClubScraper())` with:
```python
from cartelera.types import VenueDefinition, ListMembership

register(
    scraper=HarlemJazzClubScraper(),
    venue=VenueDefinition(
        slug="harlem-jazz-club",
        name="Harlem Jazz Club",
        city_slug="barcelona",
        address="Carrer de la Comtessa de Sobradiel, 8, 08002 Barcelona",
        site_url="https://www.harlemjazzclub.es",
        category_slugs=["jazz"],
        list_memberships=[
            ListMembership(list_slug="jazz"),
        ],
    ),
)
```

**`robadors.py`** — replace `register(RobadorsScraper())` with:
```python
from cartelera.types import VenueDefinition, ListMembership

register(
    scraper=RobadorsScraper(),
    venue=VenueDefinition(
        slug="robadors",
        name="23 Robadors",
        city_slug="barcelona",
        address="Carrer d'en Robador, 23, El Raval, 08001 Barcelona",
        site_url="https://23robadors.com",
        category_slugs=["jazz"],
        list_memberships=[
            ListMembership(list_slug="jazz"),
        ],
    ),
)
```

**`casa_figari.py`** — replace `register(CasaFigariScraper())` with:
```python
from cartelera.types import VenueDefinition, ListMembership

register(
    scraper=CasaFigariScraper(),
    venue=VenueDefinition(
        slug="casa-figari",
        name="Casa Figari",
        city_slug="barcelona",
        address="Carrer Torrent de l'Olla, 141, 08012 Barcelona",
        site_url="https://www.casafigari.com",
        category_slugs=["jazz", "club"],
        list_memberships=[
            ListMembership(list_slug="jazz", whitelist_category_slug="jazz"),
            ListMembership(list_slug="club", whitelist_category_slug="club"),
        ],
    ),
)
```

**`sala_beckett.py`** — replace `register(SalaBeckettScraper())` with:
```python
from cartelera.types import VenueDefinition, ListMembership

register(
    scraper=SalaBeckettScraper(),
    venue=VenueDefinition(
        slug="sala-beckett",
        name="Sala Beckett",
        city_slug="barcelona",
        address="C/ de Pere IV, 228-232, 08005 Barcelona",
        site_url="https://www.salabeckett.cat",
        category_slugs=["theater"],
        list_memberships=[
            ListMembership(list_slug="theater"),
        ],
    ),
)
```

**`big_bang.py`** — replace `register(BigBangBarScraper())` with:
```python
from cartelera.types import VenueDefinition, ListMembership

register(
    scraper=BigBangBarScraper(),
    venue=VenueDefinition(
        slug="big-bang-bar",
        name="Big Bang Bar",
        city_slug="barcelona",
        address="Carrer de la Botella, 7, El Raval, 08001 Barcelona",
        site_url="https://bigbangbar.wixsite.com/bigbang",
        category_slugs=["jazz", "club"],
        list_memberships=[
            ListMembership(list_slug="jazz", whitelist_category_slug="jazz"),
            ListMembership(list_slug="club", whitelist_category_slug="club"),
        ],
    ),
)
```

- [ ] **Step 6: Rewrite `seed.py` as a thin loop**

Replace the contents of `scraper/src/cartelera/seed.py` with:

```python
from __future__ import annotations
from sqlalchemy.orm import Session
from cartelera.models import City, Category, Venue, List, ListVenue
from cartelera.scrapers import REGISTRY
from cartelera.types import VenueDefinition

CATEGORIES = [
    ("film", "Film"),
    ("jazz", "Jazz"),
    ("classical", "Classical"),
    ("theater", "Theater"),
    ("club", "Club"),
]


def _get_or_create_city(session: Session, slug: str, name: str) -> City:
    city = session.query(City).filter_by(slug=slug).one_or_none()
    if not city:
        city = City(slug=slug, name=name)
        session.add(city)
        session.flush()
    return city


def _get_or_create_category(session: Session, slug: str, name: str) -> Category:
    cat = session.query(Category).filter_by(slug=slug).one_or_none()
    if not cat:
        cat = Category(slug=slug, name=name)
        session.add(cat)
        session.flush()
    return cat


def _get_or_create_list(session: Session, slug: str, city_id: int) -> List:
    lst = session.query(List).filter_by(slug=slug).one_or_none()
    if not lst:
        lst = List(slug=slug, name=slug.capitalize(), author="cartelera", city_id=city_id)
        session.add(lst)
        session.flush()
    return lst


def _ensure_membership(
    session: Session, list_id: int, venue_id: int, whitelist_category_id: int | None
) -> None:
    existing = (
        session.query(ListVenue)
        .filter_by(list_id=list_id, venue_id=venue_id, whitelist_category_id=whitelist_category_id)
        .one_or_none()
    )
    if not existing:
        session.add(ListVenue(list_id=list_id, venue_id=venue_id, whitelist_category_id=whitelist_category_id))


def _upsert_venue(session: Session, defn: VenueDefinition, city_id: int, cats: dict[str, Category]) -> None:
    venue = session.query(Venue).filter_by(slug=defn.slug).one_or_none()
    if not venue:
        venue = Venue(slug=defn.slug, name=defn.name, city_id=city_id, address=defn.address, site_url=defn.site_url)
        session.add(venue)
        session.flush()
    venue.categories = [cats[s] for s in defn.category_slugs if s in cats]
    for membership in defn.list_memberships:
        lst = _get_or_create_list(session, membership.list_slug, city_id)
        whitelist_id = cats[membership.whitelist_category_slug].id if membership.whitelist_category_slug else None
        _ensure_membership(session, lst.id, venue.id, whitelist_id)


def seed(session: Session) -> None:
    """Idempotent seed: ensures city, categories, and all registered venues exist."""
    bcn = _get_or_create_city(session, "barcelona", "Barcelona")
    cats = {slug: _get_or_create_category(session, slug, name) for slug, name in CATEGORIES}
    for _scraper, venue_def in REGISTRY.values():
        _upsert_venue(session, venue_def, bcn.id, cats)
    session.commit()
```

- [ ] **Step 7: Write failing tests for new seed behaviour**

In `scraper/tests/test_seed.py`, replace the file contents with:

```python
from cartelera.seed import seed
from cartelera.models import Category, Venue, List, ListVenue


def test_seed_is_idempotent(session):
    seed(session)
    seed(session)
    assert session.query(Category).count() == 5
    for slug in ("jamboree", "harlem-jazz-club", "robadors", "casa-figari", "sala-beckett", "big-bang-bar"):
        assert session.query(Venue).filter_by(slug=slug).count() == 1
    for slug in ("jazz", "club", "theater"):
        assert session.query(List).filter_by(slug=slug).count() == 1
    assert session.query(ListVenue).count() == 9


def test_jamboree_is_jazz_and_club(session):
    seed(session)
    v = session.query(Venue).filter_by(slug="jamboree").one()
    assert sorted(c.slug for c in v.categories) == ["club", "jazz"]


def test_casa_figari_is_jazz_and_club(session):
    seed(session)
    v = session.query(Venue).filter_by(slug="casa-figari").one()
    assert sorted(c.slug for c in v.categories) == ["club", "jazz"]


def test_single_category_venues(session):
    seed(session)
    harlem = session.query(Venue).filter_by(slug="harlem-jazz-club").one()
    robadors = session.query(Venue).filter_by(slug="robadors").one()
    beckett = session.query(Venue).filter_by(slug="sala-beckett").one()
    assert [c.slug for c in harlem.categories] == ["jazz"]
    assert [c.slug for c in robadors.categories] == ["jazz"]
    assert [c.slug for c in beckett.categories] == ["theater"]


def test_multi_category_venues_whitelist_their_category(session):
    seed(session)
    jazz_list = session.query(List).filter_by(slug="jazz").one()
    club_list = session.query(List).filter_by(slug="club").one()
    jazz_cat = session.query(Category).filter_by(slug="jazz").one()
    club_cat = session.query(Category).filter_by(slug="club").one()
    for venue_slug in ("jamboree", "casa-figari", "big-bang-bar"):
        v = session.query(Venue).filter_by(slug=venue_slug).one()
        jazz_mem = session.query(ListVenue).filter_by(list_id=jazz_list.id, venue_id=v.id).one()
        club_mem = session.query(ListVenue).filter_by(list_id=club_list.id, venue_id=v.id).one()
        assert jazz_mem.whitelist_category_id == jazz_cat.id
        assert club_mem.whitelist_category_id == club_cat.id


def test_single_category_venues_have_null_whitelist(session):
    seed(session)
    jazz_list = session.query(List).filter_by(slug="jazz").one()
    theater_list = session.query(List).filter_by(slug="theater").one()
    for venue_slug, lst in (("harlem-jazz-club", jazz_list),
                            ("robadors", jazz_list),
                            ("sala-beckett", theater_list)):
        v = session.query(Venue).filter_by(slug=venue_slug).one()
        mem = session.query(ListVenue).filter_by(list_id=lst.id, venue_id=v.id).one()
        assert mem.whitelist_category_id is None
```

- [ ] **Step 8: Run seed tests**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest tests/test_seed.py -v
```

Expected: all pass.

- [ ] **Step 9: Run full test suite**

```bash
cd /Users/jeroen/code/jpjagt/cartelera/scraper && uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 10: Commit**

```bash
cd /Users/jeroen/code/jpjagt/cartelera && git add scraper/pyproject.toml scraper/uv.lock scraper/src/cartelera/types.py scraper/src/cartelera/scrapers/__init__.py scraper/src/cartelera/scrapers/big_bang.py scraper/src/cartelera/scrapers/casa_figari.py scraper/src/cartelera/scrapers/harlem_jazz_club.py scraper/src/cartelera/scrapers/jamboree.py scraper/src/cartelera/scrapers/robadors.py scraper/src/cartelera/scrapers/sala_beckett.py scraper/src/cartelera/seed.py scraper/src/cartelera/run.py scraper/tests/test_seed.py
git commit -m "refactor: colocate venue definitions in scrapers; seed driven by REGISTRY"
```

---

## Task 8: Update writing-a-scraper skill with price convention

**Files:**
- Modify: `.claude/skills/writing-a-scraper` (find the exact filename below)

- [ ] **Step 1: Find the skill file**

```bash
ls /Users/jeroen/code/jpjagt/cartelera/.claude/skills/
```

- [ ] **Step 2: Add price convention section**

Open the skill file and add a "Price convention" section. Insert it after the section that describes `ScrapedEvent` fields. Content to add:

```markdown
## Price convention

The `price` field must be one of:
- `None` — price unknown or not scrape-able
- `"free"` — no admission cost (normalize locale-specific phrases: "Entrada gratuita", "Activitat gratuïta", "entrada libre", price==0, etc.)
- `"sold-out"` — tickets exhausted (normalize: "s.o.", "Sold Out", etc.)
- A concise display string — informative and short. Prefer a plain value like `"10€"` or `"10–22€"`. Skip member-tier and discount prices. Show a range only when price tiers differ meaningfully for the user.

When a price string contains multiple values (member prices, promo discounts), extract the main/highest public price.
```

- [ ] **Step 3: Commit**

```bash
cd /Users/jeroen/code/jpjagt/cartelera && git add .claude/skills/writing-a-scraper
git commit -m "docs: add price convention to writing-a-scraper skill"
```
