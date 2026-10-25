import type { Locale } from "@/lib/types"

interface Strings {
  siteTitle: string
  noEvents: string
  back: string
  andMore: string
  viewFilms: string
  viewByTime: string
  showEarlier: string
  /** Credit line under a list fed by a third-party aggregator: "Listings via <name>". */
  listingsVia: string
  myList: string
  viewEvents: string
  viewVenues: string
  favouriteVenue: string   // favourite (heart) toggle label (aria)
  pickVenues: string       // venue directory heading on My list
  share: string            // event share menu: share action + trigger label
  addToCalendar: string    // event share menu: .ics export
  copied: string           // share fallback: text copied to the clipboard
  view: string             // event panel: open the event's own page
  more: string             // navbar: the dropdown holding the quieter genres
  city: string             // navbar: city selector label (aria)
  allCities: string        // city selector: back to the city picker
  eventsHidden: string     // a collapsed day's placeholder row
  today: string            // navbar + Today page title
  todayEmpty: string       // Today: nothing (left) today for the selection
  viewList: string         // Today: list view
  viewMap: string          // Today: map view
  // Today map: venues with events today but no coordinates; {n} = count.
  notOnMapOne: string
  notOnMapMany: string
  close: string            // Today map: close the venue panel (aria)
  // Share text: {title}, {when} (date[, time]) and {venue}; " (price)" is
  // appended when there is one (lib/share.ts).
  shareTemplate: string
  // Page metadata (lib/meta.ts). inCity: "{page} in {city}", {city} in the
  // form the phrase needs (cities.ts cityNameIn).
  inCity: string
  // One-sentence description; {title} = the page's inCity phrase (Today: plus
  // the date).
  pageDescription: string
  myListDescription: string  // {city} as in inCity
  tagline: string            // the city picker's title, after "Cartelita — "
  pickerDescription: string  // {cities} = every city, as a list
  notFound: string
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
    listingsVia: "Programació via",
    myList: "La meva llista",
    viewEvents: "Esdeveniments",
    viewVenues: "Espais",
    favouriteVenue: "Espai preferit",
    pickVenues: "Marca els teus espais preferits",
    share: "Comparteix",
    addToCalendar: "Afegeix al calendari",
    copied: "Copiat",
    view: "Veure",
    more: "Més",
    city: "Ciutat",
    allCities: "Totes les ciutats",
    eventsHidden: "Esdeveniments amagats — clica per mostrar-los",
    today: "Avui",
    todayEmpty: "Avui no queda res.",
    viewList: "Llista",
    viewMap: "Mapa",
    notOnMapOne: "1 espai no surt al mapa",
    notOnMapMany: "{n} espais no surten al mapa",
    close: "Tanca",
    shareTemplate: "{title} — {when} a {venue}",
    inCity: "{page} a {city}",
    pageDescription: "{title}: una agenda triada a mà del que val la pena per sortir de casa.",
    myListDescription: "Els teus espais preferits a {city}, en una sola agenda.",
    tagline: "el que val la pena per sortir de casa",
    pickerDescription: "Agendes triades a mà per a {cities}.",
    notFound: "Pàgina no trobada",
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
      alternative: "Alternatiu",
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
    listingsVia: "Programación vía",
    myList: "Mi lista",
    viewEvents: "Eventos",
    viewVenues: "Salas",
    favouriteVenue: "Sala favorita",
    pickVenues: "Marca tus salas favoritas",
    share: "Compartir",
    addToCalendar: "Añadir al calendario",
    copied: "Copiado",
    view: "Ver",
    more: "Más",
    city: "Ciudad",
    allCities: "Todas las ciudades",
    eventsHidden: "Eventos ocultos — haz clic para mostrarlos",
    today: "Hoy",
    todayEmpty: "Hoy ya no queda nada.",
    viewList: "Lista",
    viewMap: "Mapa",
    notOnMapOne: "1 sala no aparece en el mapa",
    notOnMapMany: "{n} salas no aparecen en el mapa",
    close: "Cerrar",
    shareTemplate: "{title} — {when} en {venue}",
    inCity: "{page} en {city}",
    pageDescription: "{title}: una agenda elegida a mano de lo que merece salir de casa.",
    myListDescription: "Tus salas favoritas en {city}, en una sola agenda.",
    tagline: "lo que merece salir de casa",
    pickerDescription: "Agendas elegidas a mano para {cities}.",
    notFound: "Página no encontrada",
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
      alternative: "Alternativo",
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
    listingsVia: "Listings via",
    myList: "My list",
    viewEvents: "Events",
    viewVenues: "Venues",
    favouriteVenue: "Favourite venue",
    pickVenues: "Mark your favourite venues",
    share: "Share",
    addToCalendar: "Add to calendar",
    copied: "Copied",
    view: "View",
    more: "More",
    city: "City",
    allCities: "All cities",
    eventsHidden: "Events hidden — click to show",
    today: "Today",
    todayEmpty: "Nothing left today.",
    viewList: "List",
    viewMap: "Map",
    notOnMapOne: "1 venue not on the map",
    notOnMapMany: "{n} venues not on the map",
    close: "Close",
    shareTemplate: "{title} — {when} at {venue}",
    inCity: "{page} in {city}",
    pageDescription: "{title}: a hand-picked agenda of what's worth leaving the house for.",
    myListDescription: "Your favourite venues in {city}, in one agenda.",
    tagline: "what's on, worth leaving the house for",
    pickerDescription: "Hand-picked agendas for {cities}.",
    notFound: "Page not found",
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
      alternative: "Alternative",
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
    listingsVia: "Ծրագիրը՝",
    myList: "Իմ ցանկը",
    viewEvents: "Միջոցառումներ",
    viewVenues: "Վայրեր",
    favouriteVenue: "Սիրելի վայր",
    pickVenues: "Նշեք ձեր սիրելի վայրերը",
    share: "Կիսվել",
    addToCalendar: "Ավելացնել օրացույցին",
    copied: "Պատճենված է",
    view: "Դիտել",
    more: "Ավելին",
    city: "Քաղաք",
    allCities: "Բոլոր քաղաքները",
    eventsHidden: "Միջոցառումները թաքցված են — սեղմեք՝ ցուցադրելու համար",
    today: "Այսօր",
    todayEmpty: "Այսօր այլևս ոչինչ չկա։",
    viewList: "Ցանկ",
    viewMap: "Քարտեզ",
    notOnMapOne: "1 վայր քարտեզում չէ",
    notOnMapMany: "{n} վայր քարտեզում չեն",
    close: "Փակել",
    shareTemplate: "{title} — {when}, {venue}",
    inCity: "{page} {city}",
    pageDescription: "{title}. Ձեռքով ընտրված ծրագիր այն ամենի, ինչի համար արժե դուրս գալ տնից։",
    myListDescription: "Ձեր սիրելի վայրերը {city}՝ մեկ ծրագրում։",
    tagline: "այն, ինչի համար արժե դուրս գալ տնից",
    pickerDescription: "Ձեռքով ընտրված ծրագրեր՝ {cities}։",
    notFound: "Էջը չի գտնվել",
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
      alternative: "Ալտերնատիվ",
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
    listingsVia: "Программа через",
    myList: "Мой список",
    viewEvents: "События",
    viewVenues: "Площадки",
    favouriteVenue: "Любимая площадка",
    pickVenues: "Отметьте любимые площадки",
    share: "Поделиться",
    addToCalendar: "Добавить в календарь",
    copied: "Скопировано",
    view: "Открыть",
    more: "Ещё",
    city: "Город",
    allCities: "Все города",
    eventsHidden: "События скрыты — нажмите, чтобы показать",
    today: "Сегодня",
    todayEmpty: "На сегодня больше ничего нет.",
    viewList: "Список",
    viewMap: "Карта",
    notOnMapOne: "1 площадка не на карте",
    notOnMapMany: "Площадок не на карте: {n}",
    close: "Закрыть",
    shareTemplate: "{title} — {when}, {venue}",
    inCity: "{page} в {city}",
    pageDescription: "{title}: подборка того, ради чего стоит выйти из дома.",
    myListDescription: "Ваши любимые площадки в {city} — в одной афише.",
    tagline: "то, ради чего стоит выйти из дома",
    pickerDescription: "Афиши, собранные вручную: {cities}.",
    notFound: "Страница не найдена",
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
      alternative: "Альтернатива",
    },
    prices: { free: "Бесплатно", "sold-out": "Распродано" },
  },
  nl: {
    siteTitle: "Cartelita",
    noEvents: "Geen komende evenementen.",
    back: "Home",
    andMore: "en meer",
    viewFilms: "Per film",
    viewByTime: "Op tijd",
    showEarlier: "Toon eerdere voorstellingen",
    listingsVia: "Programma via",
    myList: "Mijn lijst",
    viewEvents: "Evenementen",
    viewVenues: "Locaties",
    favouriteVenue: "Favoriete locatie",
    pickVenues: "Markeer je favoriete locaties",
    share: "Delen",
    addToCalendar: "Toevoegen aan agenda",
    copied: "Gekopieerd",
    view: "Bekijken",
    more: "Meer",
    city: "Stad",
    allCities: "Alle steden",
    eventsHidden: "Evenementen verborgen — klik om te tonen",
    today: "Vandaag",
    todayEmpty: "Vandaag niets meer.",
    viewList: "Lijst",
    viewMap: "Kaart",
    notOnMapOne: "1 locatie niet op de kaart",
    notOnMapMany: "{n} locaties niet op de kaart",
    close: "Sluiten",
    shareTemplate: "{title} — {when} in {venue}",
    inCity: "{page} in {city}",
    pageDescription: "{title}: een handgekozen agenda van wat de deur uit gaan waard is.",
    myListDescription: "Je favoriete locaties in {city}, in één agenda.",
    tagline: "wat de deur uit gaan waard is",
    pickerDescription: "Handgekozen agenda's voor {cities}.",
    notFound: "Pagina niet gevonden",
    categories: {
      film: "Film",
      jazz: "Jazz",
      classical: "Klassiek",
      theater: "Theater",
      club: "Club",
      flamenco: "Flamenco",
      dance: "Dans",
      kids: "Kinderen",
      pop: "Pop",
      folk: "Folk",
      rock: "Rock",
      alternative: "Alternatief",
    },
    prices: { free: "Gratis", "sold-out": "Uitverkocht" },
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
  const tags = { ca: "ca-ES", es: "es-ES", en: "en-GB", hy: "hy-AM", ru: "ru-RU", nl: "nl-NL" } as const
  return tags[locale]
}

/** A yyyy-mm-dd date as the agenda's day heading spells it ("Sunday 25
    October"), independent of the build machine's time zone. */
export function longDate(locale: Locale, date: string): string {
  return new Date(date + "T12:00:00Z").toLocaleDateString(localeTag(locale), {
    weekday: "long", day: "numeric", month: "long", timeZone: "UTC",
  })
}

/** Fill a "{key}" template. */
export function fill(template: string, values: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (m, k: string) => values[k] ?? m)
}
