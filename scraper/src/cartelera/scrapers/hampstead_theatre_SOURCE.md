# Hampstead Theatre (`hampstead-theatre`)

One venue (Main Stage + Downstairs; room annotation). Category: theater.

## Data sources (website only)
- `https://www.hampsteadtheatre.com/whats-on/`: `.card--production` (title
  `.card__heading`, room class `card--venue-main-stage|downstairs`, link
  `/production/<slug>/`) with a booking dialog listing every performance:
  `li.instances-list__item[data-instances-day]` →
  `li.instances-list__time-slot__wrapper[data-time]`, labels
  (`.taxonomy-list--instance-type`: Preview kept, Press ignored),
  `data-access` (captioned / audio-described), general-booking button text
  "Sold Out" → "sold-out".
- Production page: full-price ladders "Full price: £35/£45/£55/£65",
  "Previews: £10" → one range (Seniors / Under 30s / Access excluded);
  og:image.
- external_id: `<slug>@<YYYY-MM-DDTHH:MM>`.
- TNEW `my.hampsteadtheatre.com` not read: only 105 of 184 performances
  (priority-booking ones missing). WP REST shows `production_type` = drama
  only.

## Curation
Listed productions (all theatre). Dropped: TNEW-only Portrait of a Man
(single unlisted performance).

## Verification (2026-10-25)
180 events, 100% priced. DB rows = 180. Checked: Mother Russia 2027-01-30
— listing `data-instances-day="2027-01-30"` slots 14:45 and 19:45 (16090/16141,
"Selling Fast"); page "Previews: £10", "Full Price: £28/£35" → ours 19:45
"£10–35", Downstairs.
