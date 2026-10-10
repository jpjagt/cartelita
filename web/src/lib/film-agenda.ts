import type { AgendaEvent, FilmGroup, FilmDayLayout, PackedFilm } from "@/lib/types";
import { timeSortKey } from "@/lib/agenda";
import { packCards } from "@/lib/masonry";

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

/** Build the film-day layout: grouped films plus both the 3-column and
    2-column masonry packings (CSS selects which applies per breakpoint). */
export function groupFilmDay(date: string, events: AgendaEvent[]): FilmDayLayout {
  const films = groupFilms(events);
  const layout = packCards(films.map(cardHeight));
  const packed: PackedFilm[] = films.map((film, i) => ({
    film,
    height: cardHeight(film),
    ...layout.placements[i],
  }));
  return {
    date,
    films: packed,
    rows3: layout.rows3,
    rows2: layout.rows2,
    rows1: layout.rows1,
  };
}
