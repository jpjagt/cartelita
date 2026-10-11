// Favourite venues, kept per browser in localStorage (no accounts). Stored as a
// JSON array of venue slugs; slugs are globally unique, so one set serves every
// city and locale. Every write fires FAVOURITES_EVENT on window so all hearts on
// the page and the My list filter stay in sync.

export const FAVOURITES_KEY = "favourite-venues";
export const FAVOURITES_EVENT = "favouriteschange";

/** The subset of Storage used here, so tests can pass a plain in-memory map. */
type KeyValueStore = Pick<Storage, "getItem" | "setItem">;

/** Read the favourite slugs. Missing, corrupt, or unreadable storage (private
    mode, blocked site data) all read as "no favourites". */
export function readFavourites(store: KeyValueStore): Set<string> {
  try {
    const parsed: unknown = JSON.parse(store.getItem(FAVOURITES_KEY) ?? "[]");
    return new Set(
      Array.isArray(parsed) ? parsed.filter((s) => typeof s === "string") : [],
    );
  } catch {
    return new Set();
  }
}

/** Flip one venue's favourite state, persist, and return the new set. A failed
    write (quota, blocked storage) still returns the intended set so the page
    reflects the click for this visit. */
export function toggleFavourite(store: KeyValueStore, slug: string): Set<string> {
  const favs = readFavourites(store);
  if (favs.has(slug)) favs.delete(slug);
  else favs.add(slug);
  try {
    store.setItem(FAVOURITES_KEY, JSON.stringify([...favs].sort()));
  } catch {
    // Not persisted; the in-page state still updates.
  }
  return favs;
}

let fallback: KeyValueStore | null = null;

/** localStorage, or an in-memory stand-in when it is blocked so hearts still
    toggle for the visit. Browser-only. */
export function browserStore(): KeyValueStore {
  try {
    return window.localStorage;
  } catch {
    if (!fallback) {
      const memory = new Map<string, string>();
      fallback = {
        getItem: (k) => memory.get(k) ?? null,
        setItem: (k, v) => void memory.set(k, v),
      };
    }
    return fallback;
  }
}
