import type { AgendaEvent, FilmGroup, FilmDayLayout, PackedFilm } from "@/lib/types";
import { timeSortKey } from "@/lib/agenda";

/** Drop a trailing bracketed suffix like " (VOSE)" or " [VOSE]" — version/format
    tags scrapers append to the title — so variants of the same film collapse. */
function stripBracketSuffix(title: string): string {
  return title.replace(/\s*[([][^()[\]]*[)\]]\s*$/, "").trim();
}

/** Grouping key: bracket suffix stripped and lowercased, so "El Drama (VOSE)"
    and "EL DRAMA" land in the same film. */
function filmKey(title: string): string {
  return stripBracketSuffix(title).toLowerCase();
}

function capitalCount(s: string): number {
  return (s.match(/\p{Lu}/gu) ?? []).length;
}

/** Display title for a film. The bracket suffix is only a distinguishing tag
    when the variants disagree on it; if every variant has the same full
    lowercased title (brackets included), the brackets are part of the real
    title and are kept. Among the candidate forms, pick the one with the fewest
    capital letters — so { "El Drama (VOSE)", "EL DRAMA" } → "El Drama", while
    { "The Life of (Brian)", "THE LIFE OF (BRIAN)" } → "The Life of (Brian)".
    Ties keep the first-seen variant. */
function displayTitle(titles: string[]): string {
  const allShareBrackets =
    new Set(titles.map((t) => t.toLowerCase())).size === 1;
  const candidates = allShareBrackets ? titles : titles.map(stripBracketSuffix);
  return candidates.reduce((best, cur) =>
    capitalCount(cur) < capitalCount(best) ? cur : best,
  );
}

/** Group a day's events into films (one card per title), each with its
    showtimes sorted by time; films ordered by earliest showtime. Title variants
    differing only in case or a bracketed suffix are merged (see filmKey). */
function groupFilms(events: AgendaEvent[]): FilmGroup[] {
  const buckets = new Map<string, { titles: string[]; showtimes: AgendaEvent[] }>();
  for (const ev of events) {
    const key = filmKey(ev.title);
    if (!buckets.has(key)) buckets.set(key, { titles: [], showtimes: [] });
    const b = buckets.get(key)!;
    b.titles.push(ev.title);
    b.showtimes.push(ev);
  }
  const films: FilmGroup[] = [];
  for (const { titles, showtimes } of buckets.values()) {
    showtimes.sort((a, b) =>
      timeSortKey(a.startTime).localeCompare(timeSortKey(b.startTime)),
    );
    films.push({
      title: displayTitle(titles),
      showtimes,
      earliestKey: timeSortKey(showtimes[0]?.startTime ?? null),
      latestTime: showtimes[showtimes.length - 1]?.startTime ?? "",
    });
  }
  films.sort((a, b) => a.earliestKey.localeCompare(b.earliestKey));
  return films;
}

/** Card height in cells: 1 title row + one row per showtime. */
function cardHeight(film: FilmGroup): number {
  return 1 + film.showtimes.length;
}

/** Shortest-column masonry packing over `cols` columns, in the given film
    order. Returns, per film, the chosen column and its starting row offset,
    plus the total rows consumed (the tallest column). Ties pick the leftmost
    column to preserve left-to-right reading order. */
function pack(
  films: FilmGroup[],
  cols: number,
): { placed: { col: number; row: number }[]; rows: number } {
  const heights = new Array(cols).fill(0);
  const placed = films.map((film) => {
    let col = 0;
    for (let c = 1; c < cols; c++) {
      if (heights[c] < heights[col]) col = c;
    }
    const row = heights[col];
    heights[col] += cardHeight(film) + 1; // + 1-cell gutter between cards
    return { col, row };
  });
  // Each column ends with a trailing gutter; the consumed rows is the tallest
  // column minus that final gutter (0 when there are no films).
  const rows = Math.max(0, ...heights.map((h) => Math.max(0, h - 1)));
  return { placed, rows };
}

/** Single-column (mobile) stack: cards in order, each showtime on one grid row
    (same height as desktop). Returns the row offset per film and total rows. */
function stackSingle(films: FilmGroup[]): { rows1: number[]; total: number } {
  let acc = 0;
  const rows1 = films.map((film) => {
    const at = acc;
    acc += cardHeight(film) + 1; // title + 1/showtime + gutter
    return at;
  });
  return { rows1, total: Math.max(0, acc - 1) };
}

/** Build the film-day layout: grouped films plus both the 3-column and
    2-column masonry packings (CSS selects which applies per breakpoint). */
export function groupFilmDay(date: string, events: AgendaEvent[]): FilmDayLayout {
  const films = groupFilms(events);
  const p3 = pack(films, 3);
  const p2 = pack(films, 2);
  const single = stackSingle(films);
  const packed: PackedFilm[] = films.map((film, i) => ({
    film,
    height: cardHeight(film),
    col3: p3.placed[i].col,
    row3: p3.placed[i].row,
    col2: p2.placed[i].col,
    row2: p2.placed[i].row,
    row1: single.rows1[i],
  }));
  return {
    date,
    films: packed,
    rows3: p3.rows,
    rows2: p2.rows,
    rows1: single.total,
  };
}
