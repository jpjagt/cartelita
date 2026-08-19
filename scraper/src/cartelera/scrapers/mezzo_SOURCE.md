# Mezzo Classic House Club — source map

An upscale two-storey live-music club at 28 Isahakyan St, Yerevan (open daily
15:00–01:00): classical recitals and jazz, plus blues, rock, latin and folk
nights, with live music every evening. A multi-category venue on the Jamboree
pattern — three list memberships, each whitelisted to one category
(`classical`/`jazz`/`rock`), so its nights split correctly instead of flooding
one list.

**Source type: Instagram ingest** (`cartelera/ig`), handle `@mezzoclub`. The
venue is web-dark; nothing else carries its programme (ladder below).

## Recon ladder (writing-a-scraper Phase 1, IG-only branch)

Checked **2026-08-19** (rungs 1 and 4 re-checked live today; the rest carried
over from the 2026-08-18 Yerevan recon in `docs/yerevan.md`):

| # | Rung | Result |
|---|---|---|
| 1 | **esora.app** | **Absent.** `GET /api/event-sources?city=yerevan&limit=2000` returns all 1,398 Yerevan sources; none has "mezzo" in its `name` or `instagramUsername`. (Re-run that one-liner periodically: if esora ever ingests the club, an esora scraper beats IG capture.) |
| 2 | **Link-in-bio** | Not checkable without reading the IG bio, which needs the very capture path this source implements. Re-check by hand once credentials exist. |
| 3 | **Facebook** | `facebook.com/mezzoclub` exists (page id 193298974041391, "Mezzo Classic House Club - Yerevan, Armenia") but is login-walled to plain HTTP — a fetch returns the app shell, no event data. |
| 4 | **Ticketing/aggregators** | tomsarkgh.am carries only a **restaurant** profile (`/en/restro/show/33/Mezzo-Club`: reservations — currently disabled — photos, menu, "live music every evening" blurb) with **no dated events**; the club is in no tomsarkgh event category. Nothing on ticket-am.com, toms.am or eventix.am (2026-08-18). |
| 5 | **Google Maps posts** | Not reachable from this environment (no Maps API key, browser recon unavailable per the skill's Phase 1 caveat). |
| 6 | **IG ingest** | Chosen — the floor of the ladder, because everything above is genuinely empty. |

Also dead: **`mezzo.am` is domain-squatted** (Sedo parking) — third-party
directories still print it as the venue's website; it is not. Hence
`site_url = None`.

## Handle verification (non-Instagram evidence)

`@mezzoclub`, established from sources that are not instagram.com:

1. **The venue's own YouTube channel**, `youtube.com/user/MEZZOclub`
   ("Mezzo Club"), embeds a JSON-LD `sameAs` block listing the club's own
   channels:
   `["https://www.facebook.com/mezzoclub/", "https://www.instagram.com/mezzoclub/", "https://www.tripadvisor.com/Restaurant_Review-g293932-d4501318-Reviews-MEZZO-Yerevan.html", "http://mezzo.am/", "https://twitter.com/MezzoClub"]`,
   next to a channel description that is Mezzo Yerevan's own copy ("MEZZO has
   number of jazz, rock, blues, latin and classic music bands … night–out in
   Yerevan"). This is the strongest evidence: the venue itself declares the
   handle, on a platform other than Instagram.
2. **Cross-platform username consistency**: the same `mezzoclub` vanity name on
   Facebook (`facebook.com/mezzoclub`, page id 193298974041391 = "Mezzo Classic
   House Club - Yerevan, Armenia"), YouTube and Twitter.
3. **Search-engine index**: `instagram.com/mezzoclub/` is indexed as
   "MEZZO CLUB (@mezzoclub) • Instagram photos and videos".

Not used as evidence: `mezzo.am` (squatted), and instagram.com itself (never
fetched).

⚠️ Residual risk: the YouTube channel is old, so the handle could in principle
have changed since. **First thing to check at `ig-login` time:** open
`instagram.com/mezzoclub` by hand and confirm it is the Yerevan club (28
Isahakyan St, nightly programme posts) before trusting a capture. Directory
listings for the venue (Tripadvisor, vcity.am, spyur.am, tomsarkgh) publish
address/phone/website but **no** social links, so no non-IG source states the
handle more recently.

Address (28 Isahakyan St) corroborated by vcity.am, tomsarkgh, Tripadvisor and
Yandex Maps.

## Where each field comes from

There are no CSS selectors here: every field is produced by the ingest engine
— a vision LLM reads the post's **caption and every flyer image** once
(`ig/extract.py`, `PROMPT_VERSION`), the result is stored verbatim in
`ig_post.extraction`, and `ig/source.py` maps what tonight's gate keeps.

| field | from |
|---|---|
| `title` / `description` | the extracted `contents` entry whose `lang` is `hy` (the source's `canonical_lang`), else the first entry. Extraction, never translation: only languages the post itself is written in appear. |
| `translations` | the remaining `contents` entries (first entry per language), each with the post URL as `source_url` |
| `start_date` | gate-resolved from the stated `day`/`month`/`year`. An unstated year is inferred as the nearest future one; an unresolvable date drops the event (`gate_events`) |
| `start_time` / `start_times` | extracted `time` ("HH:MM"), `None` when the post states none |
| `price` | extracted `price`, free text exactly as posted ("free", "5000֏"); `None` when unstated — never inferred |
| `language` | the **performance** language, only when the post states it |
| `category_slugs` | `[category]`, which the model must choose from this venue's list (`classical`, `jazz`, `rock`) — this is the venue's category discriminator, decided per act by the model from the hints below. Anything off-roster is dropped and logged by `source.py` (never allowed to reach the upsert's fail-fast) |
| `venue_slug` | the extracted `venue_slug`; single-venue source, so `None` is fine and off-roster values are dropped and logged |
| `image_url` | the first archived image of the post (`ig_post_image.idx = 0`), an Instagram CDN URL captured at scrape time |
| `source_url` | `https://www.instagram.com/p/{shortcode}/` |
| `external_id` | `ig-{shortcode}`, or `ig-{shortcode}-{index}` when the post announced several events — `index` is the event's position in the **stored** extraction, which is frozen at parse time (the post-gate order shifts as dates pass). A weekly line-up post is exactly this case |
| `annotations` | none: the extraction schema has no tag field |
| `recurrence_hint` | none |

**Publish gate** (`extract.gate_events`, re-run every night over every stored
extraction): `confidence >= IG_CONFIDENCE_THRESHOLD` (default 0.75), a
resolvable date, and that date inside `[today, today+6 months]` with today
taken in `Asia/Yerevan`. Every drop is logged at INFO.

**Prompt hints** (`mezzo.py: HINTS`) carry the category rule (`classical` for
recitals/chamber programmes, `jazz` for jazz/latin/funk/ethno-jazz, `rock` for
rock/blues/pop-rock), the nightly-programme post style, the
"a flyer may list a whole week → one event per date" rule, and that
dinner/reservation and birthday-party promos are not events.

## Live verification: **PENDING** ⚠️

This source has **never been run against Instagram.** It cannot be: capture
needs the scrape account's session plus the residential proxy, and neither
exists in this environment (no credentials, `ig_session` empty). Every claim
above about the *engine* is covered by tests (`tests/test_ig_source.py`,
`test_ig_capture.py`, `test_ig_extract.py`); every claim about **what this
profile actually posts** — and the handle itself — is unverified.

Once the account and `IG_PROXY_URL` exist, verify like this:

```bash
cd scraper
uv run cartelera ig-login          # once: human logs in, storage_state -> Postgres
uv run cartelera dry-run mezzo
```

`dry-run` prints:

```
[dry-run] mezzo: N events
  with start_time:  n/N (x%)
  with price:       n/N (x%)
  with image_url:   n/N (x%)
  with annotations: 0/N (0%)
  with external_id: N/N (100%)
  categories:       {'jazz': a, 'classical': b, 'rock': c}
  --- first 5 events ---
  YYYY-MM-DD HH:MM |    price | title
```

Then do the field-by-field cross-check the skill demands, against an
INDEPENDENT read of the profile (open the actual posts by hand and compare
title / date / time / price / category for the first ~6 events). Expected
shape for a club with nightly programming: near-100% `start_time` (sets start
~21:00), `image_url` 100%, categories spread across at least jazz and
classical, no duplicate `external_id`s. Watch especially for:

- **Weekly line-up flyers** — every date must produce its own event
  (`ig-{shortcode}-{n}`), or a week collapses into one row.
- **Category attribution** — the Jamboree lesson: check the model is reading
  the act, not the venue's overall vibe. A jazz-labelled rock night lands in
  the wrong list.
- **Restaurant/promo posts** must yield zero events.
- **The handle itself** (see the verification section above).

Record the result here as "Last verified: YYYY-MM-DD via …" and re-tune
`HINTS` from what you see; the extraction is cached per post, so tuning hints
only affects posts captured afterwards.

Last verified: **never** (blocked on IG credentials, 2026-08-19).
