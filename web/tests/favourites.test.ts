import { describe, it, expect } from "vitest";
import { readFavourites, toggleFavourite, FAVOURITES_KEY } from "@/lib/favourites";

function memoryStore(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
  };
}

describe("favourites", () => {
  it("reads an empty set when nothing is stored", () => {
    expect(readFavourites(memoryStore()).size).toBe(0);
  });

  it("treats corrupt or non-array storage as no favourites", () => {
    expect(readFavourites(memoryStore({ [FAVOURITES_KEY]: "{not json" })).size).toBe(0);
    expect(readFavourites(memoryStore({ [FAVOURITES_KEY]: '{"a":1}' })).size).toBe(0);
  });

  it("ignores non-string entries", () => {
    const favs = readFavourites(memoryStore({ [FAVOURITES_KEY]: '["jamboree", 3, null]' }));
    expect([...favs]).toEqual(["jamboree"]);
  });

  it("toggles a venue on and off, persisting a sorted array", () => {
    const store = memoryStore();
    expect([...toggleFavourite(store, "jamboree")]).toEqual(["jamboree"]);
    toggleFavourite(store, "bimhuis");
    expect(store.data.get(FAVOURITES_KEY)).toBe('["bimhuis","jamboree"]');
    expect([...toggleFavourite(store, "jamboree")]).toEqual(["bimhuis"]);
    expect([...readFavourites(store)]).toEqual(["bimhuis"]);
  });

  it("still returns the new set when the write fails", () => {
    const store = {
      getItem: () => null,
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    };
    expect([...toggleFavourite(store, "jamboree")]).toEqual(["jamboree"]);
  });
});
