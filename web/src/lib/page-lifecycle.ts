import type { PageDoc } from "@/lib/types";

// Per-page initialisation under Astro's <ClientRouter /> (Layout.astro).
//
// Navigation between pages swaps <body> in place instead of loading a new
// document, and every bundled module script runs ONCE per session — the first
// time a page carrying it is shown — not once per page. So a component script
// splits in two:
//  - module scope: document/window listeners (registered once, they act on
//    whatever page is current when they fire), and
//  - onPage(init): everything that reads or writes the page's own elements.
//
// onPage runs `init` once per page body, as early as it can:
//  - right away when the script evaluates (a full load: modules evaluate after
//    parsing, before `load`; a client navigation that first brings the
//    script: it evaluates after the swap, on the new body),
//  - on `astro:after-swap` (the new body is in, not yet painted — so the first
//    frame of the new page is already initialised, like a full load),
//  - on `astro:page-load` as a backstop.
// Whichever comes first wins; the others see the same body and skip.
//
// A script the next page brings may also be evaluated DURING a navigation,
// before the swap (Layout.astro preloads them so they too can initialise the
// new page on after-swap, before its first paint). Its immediate run would
// then hit the outgoing page, so between `astro:before-preparation` and
// `astro:after-swap` it waits for the swap instead.

export const BEFORE_PREPARATION = "astro:before-preparation";
export const AFTER_SWAP = "astro:after-swap";
export const PAGE_LOAD = "astro:page-load";

const navigation = new WeakMap<PageDoc, { pending: boolean }>();

/** Whether a client navigation is under way in `doc` (prepared, not yet
    swapped). Tracking starts with the first onPage call for `doc` — on every
    page, at the first load, since Layout.astro's own scripts use it. */
function navigationOf(doc: PageDoc): { pending: boolean } {
  let state = navigation.get(doc);
  if (!state) {
    const s = { pending: false };
    doc.addEventListener(BEFORE_PREPARATION, () => (s.pending = true));
    doc.addEventListener(AFTER_SWAP, () => (s.pending = false));
    navigation.set(doc, s);
    state = s;
  }
  return state;
}

export function onPage(init: () => void, doc: PageDoc = document): void {
  const nav = navigationOf(doc);
  const done = new WeakSet<object>();
  const run = () => {
    const body = doc.body;
    if (!body || done.has(body)) return;
    done.add(body);
    init();
  };
  if (!nav.pending) run();
  doc.addEventListener(AFTER_SWAP, run);
  doc.addEventListener(PAGE_LOAD, run);
}
