# Annabel — source map

Venue slug: `annabel` (Rotterdam). Categories **pop, club** (lists `pop`,
`club`, whitelisted). Schiestraat 20 — concert hall + club (+ terrace).

Site: `https://annabel.nu/` (Elementor WordPress; each event is a WP post).
Client: httpx with the Cartelita UA. One request:
`GET https://annabel.nu/wp-json/wp/v2/posts?per_page=100&_fields=id,link,title,class_list,acf,yoast_head_json.og_image`
(~22 posts — past events are unpublished, but we also filter `start_date <
today`).

## Fields (ACF on each post)

| Field | Source |
|---|---|
| `title` | `title.rendered` (HTML-unescaped) |
| `start_date` | `acf.start_date` "YYYYMMDD" |
| `start_time` | first HH:MM of `acf.tijd` ("23:00 - 04:00"; concerts state only "deuren open 19:00" → doors time) |
| `price` | `acf.ticketprijs` ("vanaf 33,-", "33,75", "Van €14,00") → `eur_price`; `acf.Ticketstatus` "uitverkocht" or `calendar.soldout` → `sold-out` |
| `category_slugs` | the post's WP category in `class_list`: `category-concert` → pop, `category-clubnacht` → club (both → both) |
| `annotations` | `acf.muziekstijl` minus "live"/"club" |
| `image_url` | `yoast_head_json.og_image[0].url` |
| `source_url` | `link` |
| `external_id` | `<post id>@<date>` |

Same fields as the detail page's "Event info" box (Datum/Tijd/Tickets).

## Exclusions

Posts in neither concert nor clubnacht (e.g. the `terras` category — Anna's
terrace) and `calendar.cancelled`.

Last verified: 2026-10-14 via HTTP cross-check (5 detail pages: Datum, Tijd,
Tickets match).
