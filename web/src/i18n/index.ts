import type { Locale } from "@/lib/types"

interface Strings {
  siteTitle: string
  noEvents: string
  back: string
  andMore: string
  viewFilms: string
  viewByTime: string
  showEarlier: string
  // category names keyed by category slug
  categories: Record<string, string>
  prices: Record<string, string>
}

const DICT: Record<Locale, Strings> = {
  ca: {
    siteTitle: "Cartelita",
    noEvents: "No hi ha esdeveniments propers.",
    back: "Inici",
    andMore: "i més",
    viewFilms: "Per pel·li",
    viewByTime: "Per hora",
    showEarlier: "Mostra sessions anteriors",
    categories: {
      film: "Cinema",
      jazz: "Jazz",
      classical: "Clàssica",
      theater: "Teatre",
      club: "Club",
      flamenco: "Flamenc",
      dance: "Dansa",
      kids: "Infantil",
      pop: "Pop",
      folk: "Folk",
      rock: "Rock",
    },
    prices: { free: "Gratuït", "sold-out": "Exhaurit" },
  },
  es: {
    siteTitle: "Cartelita",
    noEvents: "No hay eventos próximos.",
    back: "Inicio",
    andMore: "y más",
    viewFilms: "Por peli",
    viewByTime: "Por hora",
    showEarlier: "Mostrar sesiones anteriores",
    categories: {
      film: "Cine",
      jazz: "Jazz",
      classical: "Clásica",
      theater: "Teatro",
      club: "Club",
      flamenco: "Flamenco",
      dance: "Danza",
      kids: "Infantil",
      pop: "Pop",
      folk: "Folk",
      rock: "Rock",
    },
    prices: { free: "Gratis", "sold-out": "Agotado" },
  },
  en: {
    siteTitle: "Cartelita",
    noEvents: "No upcoming events.",
    back: "Home",
    andMore: "and more",
    viewFilms: "By film",
    viewByTime: "By time",
    showEarlier: "Show earlier screenings",
    categories: {
      film: "Film",
      jazz: "Jazz",
      classical: "Classical",
      theater: "Theater",
      club: "Club",
      flamenco: "Flamenco",
      dance: "Dance",
      kids: "Kids",
      pop: "Pop",
      folk: "Folk",
      rock: "Rock",
    },
    prices: { free: "Free", "sold-out": "Sold out" },
  },
  hy: {
    siteTitle: "Cartelita",
    noEvents: "Առաջիկա միջոցառումներ չկան։",
    back: "Գլխավոր",
    andMore: "և ավելին",
    viewFilms: "Ըստ ֆիլմի",
    viewByTime: "Ըստ ժամի",
    showEarlier: "Ցույց տալ ավելի վաղ սեանսները",
    categories: {
      film: "Կինո",
      jazz: "Ջազ",
      classical: "Դասական",
      theater: "Թատրոն",
      club: "Ակումբ",
      flamenco: "Ֆլամենկո",
      dance: "Պար",
      kids: "Մանկական",
      pop: "Փոփ",
      folk: "Ժողովրդական",
      rock: "Ռոք",
    },
    prices: { free: "Անվճար", "sold-out": "Սպառված" },
  },
  ru: {
    siteTitle: "Cartelita",
    noEvents: "Ближайших событий нет.",
    back: "Главная",
    andMore: "и ещё",
    viewFilms: "По фильмам",
    viewByTime: "По времени",
    showEarlier: "Показать более ранние сеансы",
    categories: {
      film: "Кино",
      jazz: "Джаз",
      classical: "Классика",
      theater: "Театр",
      club: "Клуб",
      flamenco: "Фламенко",
      dance: "Танец",
      kids: "Детям",
      pop: "Поп",
      folk: "Фолк",
      rock: "Рок",
    },
    prices: { free: "Бесплатно", "sold-out": "Распродано" },
  },
}

export function t(locale: Locale): Strings {
  return DICT[locale]
}

export function categoryName(locale: Locale, slug: string): string {
  return DICT[locale].categories[slug] ?? slug
}

/** BCP-47 tag for Intl/date formatting. */
export function localeTag(locale: Locale): string {
  const tags = { ca: "ca-ES", es: "es-ES", en: "en-GB", hy: "hy-AM", ru: "ru-RU" } as const
  return tags[locale]
}
