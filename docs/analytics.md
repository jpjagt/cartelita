# Analytics — how visitors move through Cartelita

Cartelita reports to a self-hosted **Umami** (`https://umm.july.dev`, website id
in `web/src/components/Layout.astro`). Umami counts page views on its own; on
top of that the site sends a small set of **custom events** with properties
(Umami "event data") that answer *how* people navigate: which genre tabs,
cities and locales they use, whether they open events, share them, favourite
venues, use My list, and how far ahead they look.

## Where it lives

| File | What |
| --- | --- |
| `web/src/lib/analytics.ts` | Pure helpers: logical today, day offset, buckets, referrer kind, path → city/locale/list, navigation → event. Unit-tested in `web/tests/analytics.test.ts`. |
| `web/src/lib/track.ts` | Browser side: `track(name, data)` (guarded — a no-op when Umami is blocked or not loaded), the page context, an event row's properties. |
| `web/src/components/Analytics.astro` | Site-wide listeners (in `Layout.astro`): `landing`, navigation events, `event_open`, view switches, `scroll_depth`. |
| `EventPanel`, `ShareMenu`, `FavouriteToggle`, `VenueDirectory`, `Layout` (show earlier, day toggles) | Component events, one `track(...)` call where the action happens. |

### Page views (unchanged, not sent by us)

Umami's script counts the first load and wraps `history.pushState`, so every
ClientRouter navigation is one page view. Back/forward (no pushState) is
re-stated through `replaceState` in `Layout.astro` so it counts too — exactly
one page view per page shown. The custom events never send page views.

### Why `umami.track` and not `data-umami-event` attributes

Umami v2's declarative attributes work at document level (so they would
survive client navigation), but:

- on a same-tab `<a>` Umami's handler does `preventDefault()` and then sets
  `location.href` — a **full reload** that bypasses the ClientRouter (no
  prefetch, a white flash); and
- attribute values are static strings, while most properties here are only
  known at click time (day offset, position in the day, favourite on/off,
  share outcome, whether the tap opened the panel instead).

So every event goes through `track()` in `lib/track.ts`.

## Common properties

Every event carries the page it happened on (except the navigation events,
which carry their own from/to):

| Property | Values |
| --- | --- |
| `city` | `barcelona`, `amsterdam`, … (`""` on the bare `/` city picker) |
| `locale` | `ca`, `es`, `en`, `nl`, `hy`, `ru` |
| `list` | the genre tab (`jazz`, `club`, `film` …) or `my-list` (`""` on `/`) |
| `view` | only on pages with a view switch: film `films`/`time`; My list `events`/`films`/`venues` |

Per-event properties (on `event_open`, `event_panel`, `share`, `calendar_add`,
`share_menu_open`):

| Property | Meaning |
| --- | --- |
| `category` | the event's genre (on My list each row has its own) |
| `venue` | venue slug |
| `day_offset` | days from today (agenda's logical today: before 05:00 counts as the evening before). 0 = today |
| `position` | 1-based position among the day's visible rows (film card index for a showtime) |

No titles, descriptions, prices or other free text are ever sent.

## Events

| Event | Properties | Fired when | Answers |
| --- | --- | --- | --- |
| `landing` | `source`: `direct`/`search`/`social`/`internal`/`other`; `favourites`: `0`/`1`/`2-4`/`5-9`/`10+` | once per full page load (not on client navigation), after Umami's page view | Where do visits land (city/list/locale) and from what kind of place? Are they returning, set-up visitors (have favourites)? |
| `nav_tab` | `from_list`, `to_list`, `city`, `locale`, `via` | client navigation that changes the list | Which tabs do people move between, and how (`via`)? |
| `locale_switch` | `from`, `to`, `city`, `list`, `via` | navigation that changes the locale | Who switches language, from which to which? |
| `city_switch` | `from` / `to` (`none` = the `/` picker, e.g. "All cities"), `list`, `via` | navigation that changes the city | Which cities do people pick / hop between? |
| `event_open` | `surface`: `row` (title link, wide layout) / `panel` (View in the narrow panel) / `film` (film card showtime); + per-event | outbound click (incl. middle-click) to the venue/ticket page | **The conversion.** Which lists, venues, days ahead, positions get opened? |
| `event_panel` | `action`: `open`/`close`; + per-event | narrow layout (<760px) row tap | Do mobile visitors open the panel, and then View/Share? |
| `share_menu_open` | per-event | wide layout share icon | Share menu discovery on desktop |
| `share` | `surface`: `menu`/`panel`; `result`: `shared` (OS sheet) / `dismissed` (sheet closed) / `copied` (clipboard fallback); + per-event | Share action | Do people share, natively or by copying? |
| `calendar_add` | `surface`: `menu`/`panel`; + per-event | Add to calendar | Calendar export use |
| `favourite` | `venue`, `state`: `on`/`off`, `surface`: `row` (wide event row) / `panel` (narrow panel heart) / `directory` (My list venue directory), `favourites`: count after the toggle | heart toggled | Which venues get favourited, from where; how big do lists get? |
| `my_list_view` | `view`: `events`/`films`/`venues`, `favourites` (bucket) | My list view switch by the visitor | Which My list view do people use? |
| `film_view` | `view`: `films` / `time` | film view switch | By film vs by time |
| `show_earlier` | `hidden`: number of screenings revealed | film time view "show earlier screenings" | Is the early-hide in the way? |
| `directory_card` | `category`, `state`: `collapsed`/`expanded` | My list venue directory card title | Directory card collapse use |
| `day_toggle` | `state`: `collapsed`/`expanded`, `via`: `header`/`note` (the "events hidden" row), `day_offset` | a day header toggled | Do people collapse days (and which: today?) |
| `nav_menu_open` | `menu`: `more` / `city` | a navbar dropdown opened (click or ArrowDown) | Is More / the city selector discovered? Open → pick rate: compare with `nav_tab` `via=more` / `city_switch` `via=city_menu` |
| `scroll_depth` | `max_day` (furthest day offset whose heading reached the viewport, capped at 60), `depth`: `0`/`1`/`2`/`3-6`/`7-13`/`14-29`/`30+` | once per page view, when it's left: client navigation, tab hidden (also an event opened in a new tab, app backgrounded), or unload. Not sent on pages without days | How many days ahead do people look? |

`via` (navigation events): `tab` (navbar genre tab), `more` (a tab inside the
More dropdown), `locale` (locale switcher), `city_menu` (navbar city selector),
`picker` (the `/` city picker), `logo` (wordmark), `history` (back/forward),
`link` (anything else). A control can declare its own with
`data-nav-via="…"` on it or an ancestor.

### Caveats

- `scroll_depth` is sent at the first exit signal; if a visitor opens an
  event in a new tab (tab hidden → sent) and then comes back and scrolls
  further, the later depth isn't counted.
- Events need the Umami script to have loaded (it's `defer`): a click in the
  first few hundred ms of a cold load may go unrecorded. Ad blockers block
  everything — the site works the same.
- The `/` page may redirect a returning visitor to their last city with
  `location.replace`; that visit's external referrer is lost (both Umami's
  Referrers and our `landing.source` see it as `internal`/`direct`).
- Umami's script has no `data-domains` set, so `pnpm dev` / `pnpm preview` on
  localhost **also report to production**. Consider adding
  `data-domains="cartelita.july.dev"` to the script tag in `Layout.astro`.

## Building the useful reports in Umami

All of these are in the website's **Events**, **Reports** and **Sessions**
sections. Event properties are browsable under Events → (event) → properties.

1. **Conversion: who opens events?** Reports → *Goals*: goal = event
   `event_open`. Break down with Events → `event_open` → `list`, `surface`,
   `day_offset`, `position`. Compare against page views of the same lists for
   an open rate per list.
2. **Landing → open funnel.** Reports → *Funnel*, window 30 min:
   `landing` → `nav_tab` (optional) → `event_open`. Variant for mobile:
   `event_panel` → `event_open` (filter device = mobile) shows how often an
   opened panel leads to View.
3. **Navigation paths.** Reports → *Journey* (steps 3–5, start at a list page
   such as `/barcelona/ca/jazz`): page-to-page flows. For tab-to-tab
   transitions independent of locale, use Events → `nav_tab` →
   `from_list`/`to_list`; `via` shows how much the More dropdown is used.
4. **Locales and cities.** Events → `locale_switch` (`from`→`to`),
   `city_switch` (`via` = `picker` vs `city_menu`); plus Umami's own Pages
   report grouped by URL prefix.
5. **How far ahead do people look?** Events → `scroll_depth` → `depth`
   (distribution) and the same split by `list`; `event_open` → `day_offset`
   is the "how far ahead do they actually pick" counterpart.
6. **Favourites / My list adoption.** Events → `favourite` (`state`,
   `surface`, `venue`); `landing` → `favourites` ≠ `0` is the share of
   visits by visitors who've set up My list; `my_list_view` → `view`.
7. **Sharing & calendar.** Events → `share` (`result`, `surface`) and
   `calendar_add`; Goals on each for a rate.
8. **Where they land from.** Umami's Referrers / Entry pages, plus
   `landing` → `source` × `city`/`list`.
9. **Retention.** Reports → *Retention* (Umami's own session ids); segment
   with a filter on `landing.favourites`.

## Privacy

No personal data is sent: no titles or free text, no user ids, no
`umami.identify`, no extra cookies or cross-site identifiers — properties are
genre/city/locale/venue slugs, small counts and buckets. Umami itself is
cookieless (sessions are a salted hash on its server) and the site's favourites stay
in the visitor's own `localStorage`; only their *count* (bucketed on
`landing`/`my_list_view`) and the toggled venue slug leave the browser.
