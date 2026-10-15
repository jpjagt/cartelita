import { sql } from "@/lib/db"
import { excerpt } from "@/lib/description"
import { FILM_LIST, NAV_WINDOW_DAYS, orderByVolume } from "@/lib/genre-nav"
import type {
  CategoryList,
  AgendaEvent,
  CityAgendaEvent,
  Locale,
  VenueGroup,
} from "@/lib/types"
import type { TodayEvent, TodayVenue } from "@/types/today"

interface EventRow {
  id: number
  start_date: Date | string
  start_time: string | null
  start_times: string[] | null
  recurrence_hint: string | null
  venue_slug: string
  venue_name: string
  price: string | null
  language: string | null
  title: string
  description: string | null
  source_url: string
}

const lists = new Map<string, Promise<CategoryList[]>>()

/** A city's cartelera lists, busiest first (lib/genre-nav.ts orderByVolume):
    each with its event count over the next NAV_WINDOW_DAYS — the same
    membership + whitelist rule as getEventsForList. Memoised per build: every
    page's navbar asks. */
export function getCategoryLists(citySlug: string): Promise<CategoryList[]> {
  let hit = lists.get(citySlug)
  if (!hit) {
    hit = queryCategoryLists(citySlug)
    lists.set(citySlug, hit)
  }
  return hit
}

async function queryCategoryLists(citySlug: string): Promise<CategoryList[]> {
  // List slugs are unique per city (each city has its own "jazz" list).
  const rows = await sql<{ slug: string; upcoming: number }[]>`
    SELECT l.slug, count(DISTINCT e.id)::int AS upcoming
    FROM list l
    JOIN city c ON c.id = l.city_id
    LEFT JOIN list_venue lv ON lv.list_id = l.id
    LEFT JOIN event e ON e.venue_id = lv.venue_id
      AND e.hidden_at IS NULL
      AND e.start_date >= CURRENT_DATE
      AND e.start_date < CURRENT_DATE + ${NAV_WINDOW_DAYS}::int
      AND (
        lv.whitelist_category_id IS NULL
        OR EXISTS (
          SELECT 1 FROM event_category ec
          WHERE ec.event_id = e.id AND ec.category_id = lv.whitelist_category_id
        )
      )
    WHERE l.author = 'cartelera' AND c.slug = ${citySlug}
    GROUP BY l.slug`
  return orderByVolume(rows.map((r) => ({ slug: r.slug, upcoming: Number(r.upcoming) })))
}

function toDateStr(v: Date | string): string {
  return v instanceof Date
    ? v.toISOString().slice(0, 10)
    : String(v).slice(0, 10)
}

export async function getEventsForList(
  citySlug: string,
  listSlug: string,
  locale: Locale,
): Promise<AgendaEvent[]> {
  // Events from the list's venues, applying each membership's optional category
  // whitelist, from today onward, chronological. Hidden events (presumed
  // cancelled by scraper health; never deleted) are excluded everywhere.
  // Content is resolved per locale: the matching event_translation if present,
  // else the canonical event fields.
  // Lists are addressed as (city, slug): slugs are only unique per city.
  const rows = await sql<EventRow[]>`
    SELECT DISTINCT e.id, e.start_date, e.start_time, e.start_times, e.recurrence_hint,
                    v.slug AS venue_slug, v.name AS venue_name, e.price, e.language,
                    COALESCE(t.title, e.title)              AS title,
                    COALESCE(t.description, e.description)  AS description,
                    COALESCE(t.source_url, e.source_url)    AS source_url
    FROM list l
    JOIN city c ON c.id = l.city_id
    JOIN list_venue lv ON lv.list_id = l.id
    JOIN venue v ON v.id = lv.venue_id
    JOIN event e ON e.venue_id = v.id AND e.start_date >= CURRENT_DATE - INTERVAL '1 day' AND e.hidden_at IS NULL
    LEFT JOIN event_translation t ON t.event_id = e.id AND t.lang = ${locale}
    WHERE c.slug = ${citySlug}
      AND l.slug = ${listSlug}
      AND (
        lv.whitelist_category_id IS NULL
        OR EXISTS (
          SELECT 1 FROM event_category ec
          WHERE ec.event_id = e.id AND ec.category_id = lv.whitelist_category_id
        )
      )
    ORDER BY e.start_date, e.start_time NULLS FIRST, e.id`

  return expandShowtimes(rows, (r, base) => base)
}

/** Expand one agenda row per showtime: an event with start_times
    [19:00, 21:00] renders as two lines. Events with no times yield a single
    timeless row. start_times is always populated when start_time is set, but
    fall back to the scalar (then null) to stay robust to older rows. The
    result is re-sorted by (date, time): a multi-showtime event's later sessions
    must interleave with other events by their real time, not stay pinned to
    the event's earliest-session ordering position. Timeless rows sort first.
    `extend` adds query-specific fields to each expanded row. */
function expandShowtimes<R extends EventRow, T extends AgendaEvent>(
  rows: R[],
  extend: (row: R, base: AgendaEvent) => T,
): T[] {
  const expanded = rows.flatMap((r) => {
    const times = r.start_times?.length
      ? r.start_times
      : r.start_time
        ? [r.start_time]
        : [null]
    return times.map((time) =>
      extend(r, {
        id: r.id,
        title: r.title,
        startDate: toDateStr(r.start_date),
        startTime: time ? String(time).slice(0, 5) : null,
        venueSlug: r.venue_slug,
        venueName: r.venue_name,
        price: r.price,
        sourceUrl: r.source_url,
        recurrenceHint: r.recurrence_hint,
        language: r.language,
        description: excerpt(r.description),
      }),
    )
  })
  expanded.sort(
    (a, b) =>
      a.startDate.localeCompare(b.startDate) ||
      (a.startTime ?? "").localeCompare(b.startTime ?? ""),
  )
  return expanded
}

interface CityEventRow extends EventRow {
  list_slugs: string[]
}

export async function getCityEvents(
  citySlug: string,
  locale: Locale,
): Promise<CityAgendaEvent[]> {
  // Every upcoming event in the city that some cartelera list shows — the same
  // membership + whitelist rule as getEventsForList, so events no list curates
  // (e.g. a venue's off-genre rentals) stay hidden here too. Each event comes
  // once, with the slugs of the lists it appears in: those pick the hover tint
  // and whether it belongs to the Films view.
  const rows = await sql<CityEventRow[]>`
    SELECT e.id, e.start_date, e.start_time, e.start_times, e.recurrence_hint,
           v.slug AS venue_slug, v.name AS venue_name, e.price, e.language,
           COALESCE(t.title, e.title)              AS title,
           COALESCE(t.description, e.description)  AS description,
           COALESCE(t.source_url, e.source_url)    AS source_url,
           array_agg(DISTINCT l.slug)              AS list_slugs
    FROM list l
    JOIN city c ON c.id = l.city_id
    JOIN list_venue lv ON lv.list_id = l.id
    JOIN venue v ON v.id = lv.venue_id
    JOIN event e ON e.venue_id = v.id AND e.start_date >= CURRENT_DATE - INTERVAL '1 day' AND e.hidden_at IS NULL
    LEFT JOIN event_translation t ON t.event_id = e.id AND t.lang = ${locale}
    WHERE c.slug = ${citySlug}
      AND l.author = 'cartelera'
      AND (
        lv.whitelist_category_id IS NULL
        OR EXISTS (
          SELECT 1 FROM event_category ec
          WHERE ec.event_id = e.id AND ec.category_id = lv.whitelist_category_id
        )
      )
    GROUP BY e.id, v.slug, v.name, t.title, t.description, t.source_url
    ORDER BY e.start_date, e.start_time NULLS FIRST, e.id`

  // An event in several lists tints by the busiest of them (navbar order).
  const order = (await getCategoryLists(citySlug)).map((l) => l.slug)
  const tint = (listSlugs: string[]) =>
    order.find((s) => listSlugs.includes(s)) ?? [...listSlugs].sort()[0]
  return expandShowtimes(rows, (r, base) => ({
    ...base,
    genre: tint(r.list_slugs),
    isFilm: r.list_slugs.includes(FILM_LIST),
  }))
}

interface TodayEventRow extends CityEventRow {
  end_date: Date | string | null
  end_time: string | null
  venue_lat: number | null
  venue_lng: number | null
}

/** The Today page's agenda: every curated event in the city (the same rule
    as getCityEvents; each event once, with all its lists) whose logical day
    falls in [from, from + days) — the query takes a day either side, the
    caller groups by logical day — plus its end and its venue's coordinates.
    `from` is the city's logical today at build time (lib/today.ts). */
export async function getTodayAgenda(
  citySlug: string,
  locale: Locale,
  from: string,
  days: number,
): Promise<{ events: TodayEvent[]; venues: Record<string, TodayVenue> }> {
  const rows = await sql<TodayEventRow[]>`
    SELECT e.id, e.start_date, e.start_time, e.start_times, e.recurrence_hint,
           e.end_date, e.end_time,
           v.slug AS venue_slug, v.name AS venue_name, v.lat AS venue_lat, v.lng AS venue_lng,
           e.price, e.language,
           COALESCE(t.title, e.title)              AS title,
           COALESCE(t.description, e.description)  AS description,
           COALESCE(t.source_url, e.source_url)    AS source_url,
           array_agg(DISTINCT l.slug)              AS list_slugs
    FROM list l
    JOIN city c ON c.id = l.city_id
    JOIN list_venue lv ON lv.list_id = l.id
    JOIN venue v ON v.id = lv.venue_id
    JOIN event e ON e.venue_id = v.id
      AND e.start_date >= ${from}::date
      AND e.start_date <= ${from}::date + ${days}::int
      AND e.hidden_at IS NULL
    LEFT JOIN event_translation t ON t.event_id = e.id AND t.lang = ${locale}
    WHERE c.slug = ${citySlug}
      AND l.author = 'cartelera'
      AND (
        lv.whitelist_category_id IS NULL
        OR EXISTS (
          SELECT 1 FROM event_category ec
          WHERE ec.event_id = e.id AND ec.category_id = lv.whitelist_category_id
        )
      )
    GROUP BY e.id, v.slug, v.name, v.lat, v.lng, t.title, t.description, t.source_url
    ORDER BY e.start_date, e.start_time NULLS FIRST, e.id`

  const order = (await getCategoryLists(citySlug)).map((l) => l.slug)
  const tint = (listSlugs: string[]) =>
    order.find((s) => listSlugs.includes(s)) ?? [...listSlugs].sort()[0]
  const venues: Record<string, TodayVenue> = {}
  for (const r of rows) {
    venues[r.venue_slug] = {
      n: r.venue_name,
      lat: r.venue_lat === null ? null : Number(r.venue_lat),
      lng: r.venue_lng === null ? null : Number(r.venue_lng),
    }
  }
  const events = expandShowtimes(rows, (r, base) => ({
    ...base,
    genre: tint(r.list_slugs),
    isFilm: r.list_slugs.includes(FILM_LIST),
    lists: [...r.list_slugs].sort(),
    endDate: r.end_date === null ? null : toDateStr(r.end_date),
    endTime: r.end_time ? String(r.end_time).slice(0, 5) : null,
    multi: (r.start_times?.length ?? 0) > 1,
  }))
  return { events, venues }
}

export async function getVenueDirectory(citySlug: string): Promise<VenueGroup[]> {
  // The city's category lists (navbar order), each with its venues by name. A
  // venue sits in every list it is a member of (Jamboree: jazz and club).
  const lists = await getCategoryLists(citySlug)
  const rows = await sql<{ list_slug: string; slug: string; name: string }[]>`
    SELECT DISTINCT l.slug AS list_slug, v.slug, v.name
    FROM list l
    JOIN city c ON c.id = l.city_id
    JOIN list_venue lv ON lv.list_id = l.id
    JOIN venue v ON v.id = lv.venue_id
    WHERE l.author = 'cartelera' AND c.slug = ${citySlug}
    ORDER BY v.name`
  return lists.map((l) => ({
    listSlug: l.slug,
    venues: rows
      .filter((r) => r.list_slug === l.slug)
      .map((r) => ({ slug: r.slug, name: r.name })),
  }))
}
