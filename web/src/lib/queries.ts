import { sql } from "@/lib/db"
import type {
  CategoryList,
  AgendaEvent,
  CityAgendaEvent,
  Locale,
  VenueGroup,
} from "@/lib/types"

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
  source_url: string
}

// Broad-appeal genres, in display order. These lead the navbar at full weight;
// everything else (pop, flamenco, kids, …) trails after and renders muted so the
// eye skips past it without the niche genres being hidden behind a control.
const PRIMARY_LIST_ORDER = ["jazz", "classical", "theater", "film", "dance"]

// Events in the film list go to My list's Films view rather than Events.
const FILM_LIST = "film"

export async function getCategoryLists(citySlug: string): Promise<CategoryList[]> {
  // List slugs are unique per city (each city has its own "jazz" list).
  const rows = await sql<{ slug: string }[]>`
    SELECT l.slug FROM list l
    JOIN city c ON c.id = l.city_id
    WHERE l.author = 'cartelera' AND c.slug = ${citySlug}`
  return rows
    .map((r) => ({
      slug: r.slug,
      primary: PRIMARY_LIST_ORDER.includes(r.slug),
    }))
    .sort((a, b) => {
      const ai = PRIMARY_LIST_ORDER.indexOf(a.slug)
      const bi = PRIMARY_LIST_ORDER.indexOf(b.slug)
      if (ai !== -1 && bi !== -1) return ai - bi
      if (ai !== -1) return -1
      if (bi !== -1) return 1
      return a.slug.localeCompare(b.slug)
    })
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
  // whitelist, from today onward, chronological. Content is resolved per locale:
  // the matching event_translation if present, else the canonical event fields.
  // Lists are addressed as (city, slug): slugs are only unique per city.
  const rows = await sql<EventRow[]>`
    SELECT DISTINCT e.id, e.start_date, e.start_time, e.start_times, e.recurrence_hint,
                    v.slug AS venue_slug, v.name AS venue_name, e.price, e.language,
                    COALESCE(t.title, e.title)            AS title,
                    COALESCE(t.source_url, e.source_url)  AS source_url
    FROM list l
    JOIN city c ON c.id = l.city_id
    JOIN list_venue lv ON lv.list_id = l.id
    JOIN venue v ON v.id = lv.venue_id
    JOIN event e ON e.venue_id = v.id AND e.start_date >= CURRENT_DATE - INTERVAL '1 day'
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
           COALESCE(t.title, e.title)            AS title,
           COALESCE(t.source_url, e.source_url)  AS source_url,
           array_agg(DISTINCT l.slug)            AS list_slugs
    FROM list l
    JOIN city c ON c.id = l.city_id
    JOIN list_venue lv ON lv.list_id = l.id
    JOIN venue v ON v.id = lv.venue_id
    JOIN event e ON e.venue_id = v.id AND e.start_date >= CURRENT_DATE - INTERVAL '1 day'
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
    GROUP BY e.id, v.slug, v.name, t.title, t.source_url
    ORDER BY e.start_date, e.start_time NULLS FIRST, e.id`

  return expandShowtimes(rows, (r, base) => ({
    ...base,
    genre: primaryGenre(r.list_slugs),
    isFilm: r.list_slugs.includes(FILM_LIST),
  }))
}

/** The list slug that tints an event on a mixed page: the first primary genre
    it appears in, else any. */
function primaryGenre(listSlugs: string[]): string {
  return (
    PRIMARY_LIST_ORDER.find((s) => listSlugs.includes(s)) ??
    [...listSlugs].sort()[0]
  )
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
