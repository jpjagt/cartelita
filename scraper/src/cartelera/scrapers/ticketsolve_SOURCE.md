# Ticketsolve (shared helper `_ticketsolve.py`) — source map

Ticketsolve is a box-office system used by many UK and Irish theatres,
halls and arts centres. Every client publishes its programme as public
XML, no key, plain httpx with `CARTELITA_COMPAT_UA`.

## Endpoints

| Call | Use |
|---|---|
| `GET https://<client>.ticketsolve.com/shows.xml` (or the client's custom domain) | `venues/venue` (`name`) → `shows/show` (`id`, `name`, `description` HTML, `event_category`, `production_company_name`, `url`, `tags/tag`, `images/image/url[@size]`) → `events/event` (`id`, `date_time_iso` with offset, `opening_time_iso`, `event_attribute`, `venue_layout`, `url`, `status`, `feed/url`) — **one event per performance** |
| `GET …/shows/<show>/events/<event>.xml` | the performance's `prices/price` (`type`, `face_price`, `selling_price`), `available`, `capacity`, `duration` (~2 KB) |

## Fields

| Field | Source |
|---|---|
| `title` | show `name` |
| `start_date`/`start_time` | event `date_time_iso` → Europe/London |
| `external_id` | event `id` (per performance) |
| `source_url` | event `url` (the Ticketsolve booking page for that performance) |
| `price` | event feed: the max of the price types named Standard / Full Price / General Admission / Adult when there is one (Conway Hall "Supporter £20 / Standard £14 / …" → "£14"; "Full Price £40 / Concession £35" → "£40"), else every paid tier through `format_gbp_range` (a pay-what-you-can ladder £5…£25 → "£5–25"); all £0 → "free"; status "sold out" → "sold-out" without asking the feed |
| `description` | show `description` (HTML → text) |
| `image_url` | the show's large image |
| `annotations` | `event_attribute` lowercased ("preview", "pay what you can", "relaxed show", "captioned performance"); "In Person" is not a label |

Always dropped: performances before today, cancelled ones, and online
streams (`event_attribute` "Online" or `venue_layout` "ONLINE" — Conway
Hall sells each talk as an In Person and an Online performance).
Curation beyond that is the venue module's `keep(show, performance)`.

## Venues on this helper

| Module | Feed | Curation |
|---|---|---|
| `conway_hall.py` | `conwayhall.ticketsolve.com` | `event_category` = Sunday Concerts → classical |
| `new_diorama_theatre.py` | `newdiorama-tickets.newdiorama.com` | everything at feed venue "New Diorama Theatre" → theater |
| `jermyn_street_theatre.py` | `jermynstreettheatre.ticketsolve.com` | everything at feed venue "Jermyn Street Theatre" → theater |

Other Ticketsolve clients spotted in the London research: Theatre Peckham,
David Lean Cinema.
