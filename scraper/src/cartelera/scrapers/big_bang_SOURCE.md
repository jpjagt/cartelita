# Big Bang Bar — Source Map

**Site**: https://bigbangbar.wixsite.com/bigbang  
**Type**: Static Wix site — same weekly schedule repeats every week, no per-event pages.

## List URL

`https://bigbangbar.wixsite.com/bigbang` (the homepage itself)

## Data source

The page is server-side rendered by Wix and contains the full schedule in `innerText`.
Content is in `.wixui-rich-text` elements; no JSON-LD carries event data.

Since the schedule is 100% static/recurring, the scraper hard-codes the weekly template
and generates concrete dated occurrences for the next 14 days from today.

## Weekly template

| Day       | Title                    | Time  | Price            | Category | Notes                        |
|-----------|--------------------------|-------|------------------|----------|------------------------------|
| Monday    | Big Bang Open Mic        | 21:00 | Entrada gratuita | jazz     | Rock/Blues/Pop open mic      |
| Tuesday   | Raval Music              | 21:00 | Entrada gratuita | jazz     | Rotating local artists       |
| Wednesday | Big Bang Open Mic        | 20:30 | Entrada gratuita | jazz     | Rock/Blues/Pop open mic      |
| Thursday  | Big Bang Open Mic        | 20:30 | Entrada gratuita | jazz     | Same slot as Wednesday       |
| Friday    | Jam Session de Jazz      | 21:00 | Entrada gratuita | jazz     |                              |
| Friday    | Dj Session               | 00:00 | Entrada gratuita | club     | Midnight DJ after Jazz Jam   |
| Saturday  | New Orleans Jazz Jam     | 21:00 | Entrada gratuita | jazz     | Concierto + Jam Session      |
| Saturday  | Dj Session               | 00:00 | Entrada gratuita | club     | Midnight DJ after Jazz Jam   |
| Sunday    | Big Bang Open Mic        | 20:00 | Entrada gratuita | jazz     | Rock/Blues/Pop open mic      |

Friday/Saturday midnight DJ sessions use `start_time=None` (00:00 is the all-day sentinel
meaning "time unknown") and are tagged as `club`. The jazz sessions have explicit times.

## external_id

`<venue_slug>-<YYYY-MM-DD>-<slug>` — constructed from date + title slug.

## Category mapping

- Open Mic, Raval Music, Jazz Jam → `jazz`
- Dj Session → `club`

## Verification

Last verified: 2026-06-01 — all 9 weekly slots match the live page exactly.
