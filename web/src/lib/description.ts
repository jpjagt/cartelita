// Event descriptions ship only as a short excerpt: the narrow layout's event
// panel shows ~3 lines of it, and the full text would bloat 5,000-row pages.

/** Default excerpt length, in characters (≈3 lines on a 760px-wide panel). */
export const DESCRIPTION_CHARS = 240;

/** Collapse whitespace and cut to at most `max` characters at a word boundary,
    ending in "…" when anything was dropped. Empty/null → null. */
export function excerpt(
  text: string | null | undefined,
  max = DESCRIPTION_CHARS,
): string | null {
  const flat = (text ?? "").replace(/\s+/g, " ").trim();
  if (!flat) return null;
  if (flat.length <= max) return flat;
  const cut = flat.slice(0, max - 1);
  const space = cut.lastIndexOf(" ");
  // A single huge word (a URL) has no boundary worth keeping: hard-cut it.
  const head = space > max / 2 ? cut.slice(0, space) : cut;
  return head.replace(/[\s.,;:!?¡¿—–-]+$/u, "") + "…";
}
