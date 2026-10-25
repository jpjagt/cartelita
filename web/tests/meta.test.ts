import { describe, it, expect } from "vitest";
import { CITIES } from "@/lib/cities";
import {
  cityAlternates, inCity, listMeta, myListMeta, notFoundMeta, ogImagePath, ogLocale,
  pickerMeta, todayMeta, SITE_OG_IMAGE,
} from "@/lib/meta";

const { london, barcelona, yerevan, amsterdam } = CITIES;

describe("page titles name the city, the page and Cartelita", () => {
  it("list pages, in each locale's grammar", () => {
    expect(listMeta(london, "en", "theater").title).toBe("Theater in London — Cartelita");
    expect(listMeta(barcelona, "ca", "jazz").title).toBe("Jazz a Barcelona — Cartelita");
    expect(listMeta(barcelona, "es", "classical").title).toBe("Clásica en Barcelona — Cartelita");
    expect(listMeta(amsterdam, "nl", "film").title).toBe("Film in Amsterdam — Cartelita");
    // Armenian locative, Russian prepositional.
    expect(listMeta(yerevan, "hy", "jazz").title).toBe("Ջազ Երևանում — Cartelita");
    expect(listMeta(yerevan, "ru", "jazz").title).toBe("Джаз в Ереване — Cartelita");
    expect(listMeta(yerevan, "en", "jazz").title).toBe("Jazz in Yerevan — Cartelita");
  });

  it("Today and My list", () => {
    expect(todayMeta(london, "en", "2026-10-25").title).toBe("Today in London — Cartelita");
    expect(todayMeta(yerevan, "ru", "2026-10-25").title).toBe("Сегодня в Ереване — Cartelita");
    expect(myListMeta(london, "en").title).toBe("My list · London — Cartelita");
    expect(myListMeta(yerevan, "hy").title).toBe("Իմ ցանկը · Երևան — Cartelita");
  });

  it("the city picker and 404", () => {
    expect(pickerMeta().title).toBe("Cartelita — what's on, worth leaving the house for");
    expect(notFoundMeta().title).toBe("Page not found — Cartelita");
  });
});

describe("descriptions", () => {
  it("say what the page is, where", () => {
    expect(listMeta(london, "en", "theater").description).toBe(
      "Theater in London: a hand-picked agenda of what's worth leaving the house for.",
    );
    expect(myListMeta(barcelona, "es").description).toBe("Tus salas favoritas en Barcelona, en una sola agenda.");
  });

  it("Today's carries the day", () => {
    expect(todayMeta(london, "en", "2026-10-25").description).toContain("Today in London, Sunday 25 October:");
    expect(todayMeta(barcelona, "ca", "2026-10-25").description).toContain("Avui a Barcelona, diumenge");
  });

  it("the picker lists every city", () => {
    const d = pickerMeta().description;
    for (const c of Object.values(CITIES)) expect(d).toContain(c.name);
  });
});

describe("urls and images", () => {
  it("canonical, OG image and alternates of a city page", () => {
    const m = listMeta(barcelona, "es", "jazz");
    expect(m.canonical).toBe("/barcelona/es/jazz");
    expect(m.ogImage).toBe("/og/barcelona-es-jazz.png");
    expect(m.ogImageAlt).toBe(m.title);
    expect(m.alternates).toEqual([
      { hreflang: "ca", path: "/barcelona/ca/jazz" },
      { hreflang: "es", path: "/barcelona/es/jazz" },
      { hreflang: "en", path: "/barcelona/en/jazz" },
      { hreflang: "x-default", path: "/barcelona/ca/jazz" },
    ]);
  });

  it("Today and My list have their own images", () => {
    expect(todayMeta(london, "en", "2026-10-25").ogImage).toBe(ogImagePath("london", "en", "today"));
    expect(myListMeta(london, "en").ogImage).toBe("/og/london-en-my-list.png");
    expect(cityAlternates(london, "today")).toHaveLength(2); // en + x-default
  });

  it("the picker and 404 share the site image; 404 is noindex without canonical", () => {
    expect(pickerMeta().ogImage).toBe(SITE_OG_IMAGE);
    const nf = notFoundMeta();
    expect(nf.ogImage).toBe(SITE_OG_IMAGE);
    expect(nf.noindex).toBe(true);
    expect(nf.canonical).toBeUndefined();
    expect(nf.url).toBe("/");
  });

  it("og:locale", () => {
    expect(ogLocale("en")).toBe("en_GB");
    expect(ogLocale("hy")).toBe("hy_AM");
  });

  it("inCity falls back to the config name", () => {
    expect(inCity(CITIES.asuncion, "es", "Cine")).toBe("Cine en Asunción");
  });
});
