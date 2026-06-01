import { sql } from "@/lib/db";
import type { CategoryList, AgendaEvent, Locale } from "@/lib/types";

interface EventRow {
  id: number;
  start_date: Date | string;
  start_time: string | null;
  recurrence_hint: string | null;
  venue_name: string;
  price: string | null;
  title: string;
  source_url: string;
}

export async function getCategoryLists(): Promise<CategoryList[]> {
  const rows = await sql<{ slug: string }[]>`
    SELECT slug FROM list WHERE author = 'cartelera' ORDER BY slug`;
  return rows.map((r) => ({ slug: r.slug }));
}

function toDateStr(v: Date | string): string {
  return v instanceof Date ? v.toISOString().slice(0, 10) : String(v).slice(0, 10);
}

export async function getEventsForList(listSlug: string, locale: Locale): Promise<AgendaEvent[]> {
  // Events from the list's venues, applying each membership's optional category
  // whitelist, from today onward, chronological. Content is resolved per locale:
  // the matching event_translation if present, else the canonical event fields.
  const rows = await sql<EventRow[]>`
    SELECT DISTINCT e.id, e.start_date, e.start_time, e.recurrence_hint,
                    v.name AS venue_name, e.price,
                    COALESCE(t.title, e.title)            AS title,
                    COALESCE(t.source_url, e.source_url)  AS source_url
    FROM list l
    JOIN list_venue lv ON lv.list_id = l.id
    JOIN venue v ON v.id = lv.venue_id
    JOIN event e ON e.venue_id = v.id AND e.start_date >= CURRENT_DATE
    LEFT JOIN event_translation t ON t.event_id = e.id AND t.lang = ${locale}
    WHERE l.slug = ${listSlug}
      AND (
        lv.whitelist_category_id IS NULL
        OR EXISTS (
          SELECT 1 FROM event_category ec
          WHERE ec.event_id = e.id AND ec.category_id = lv.whitelist_category_id
        )
      )
    ORDER BY e.start_date, e.start_time NULLS FIRST`;

  return rows.map((r) => ({
    id: r.id,
    title: r.title,
    startDate: toDateStr(r.start_date),
    startTime: r.start_time ? String(r.start_time).slice(0, 5) : null,
    venueName: r.venue_name,
    price: r.price,
    sourceUrl: r.source_url,
    recurrenceHint: r.recurrence_hint,
  }));
}
