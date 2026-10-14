import { describe, it, expect } from "vitest";
import { onPage, AFTER_SWAP, BEFORE_PREPARATION, PAGE_LOAD } from "@/lib/page-lifecycle";

// A stand-in document: an event target whose body a "navigation" replaces.
function fakeDoc() {
  const target = new EventTarget();
  return {
    body: {} as object | null,
    addEventListener: (type: string, fn: () => void) => target.addEventListener(type, fn),
    fire: (type: string) => target.dispatchEvent(new Event(type)),
  };
}

describe("onPage", () => {
  it("runs immediately for the current page", () => {
    const doc = fakeDoc();
    let runs = 0;
    onPage(() => runs++, doc);
    expect(runs).toBe(1);
  });

  it("does not re-run on page-load for the page it already initialised (full load)", () => {
    const doc = fakeDoc();
    let runs = 0;
    onPage(() => runs++, doc);
    doc.fire(PAGE_LOAD);
    expect(runs).toBe(1);
  });

  it("runs once per navigation: after-swap, then page-load skips the same body", () => {
    const doc = fakeDoc();
    let runs = 0;
    onPage(() => runs++, doc);
    doc.body = {};
    doc.fire(AFTER_SWAP);
    doc.fire(PAGE_LOAD);
    expect(runs).toBe(2);
    doc.body = {};
    doc.fire(AFTER_SWAP);
    doc.fire(PAGE_LOAD);
    expect(runs).toBe(3);
  });

  it("falls back to page-load when no after-swap reached it", () => {
    const doc = fakeDoc();
    let runs = 0;
    onPage(() => runs++, doc);
    doc.body = {};
    doc.fire(PAGE_LOAD);
    expect(runs).toBe(2);
  });

  it("waits when there is no body yet", () => {
    const doc = fakeDoc();
    doc.body = null;
    let runs = 0;
    onPage(() => runs++, doc);
    expect(runs).toBe(0);
    doc.body = {};
    doc.fire(PAGE_LOAD);
    expect(runs).toBe(1);
  });

  it("defers a script evaluated mid-navigation to the incoming page", () => {
    const doc = fakeDoc();
    onPage(() => {}, doc); // the layout's scripts, from the first load
    doc.fire(BEFORE_PREPARATION);
    const outgoing = doc.body;
    const seen: object[] = [];
    onPage(() => seen.push(doc.body!), doc); // preloaded during the navigation
    expect(seen).toEqual([]);
    doc.body = {};
    doc.fire(AFTER_SWAP);
    doc.fire(PAGE_LOAD);
    expect(seen).toEqual([doc.body]);
    expect(seen[0]).not.toBe(outgoing);
  });

  it("runs immediately again once the navigation has swapped", () => {
    const doc = fakeDoc();
    onPage(() => {}, doc);
    doc.fire(BEFORE_PREPARATION);
    doc.body = {};
    doc.fire(AFTER_SWAP);
    let runs = 0;
    onPage(() => runs++, doc); // first brought by this navigation, run by the router
    expect(runs).toBe(1);
  });
});
