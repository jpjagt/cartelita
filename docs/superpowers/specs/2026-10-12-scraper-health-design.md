# Scraper health, pruning and repair queue — design

Date: 2026-10-12. Extends the 2026-06-01 design (§ scraper service: "graceful
degradation", "structured run reporting", repair-flow-ready) and
`docs/future-features.md` ("autonomous scraper auto-repair" stays deferred: this
is the human-in-the-loop version it describes).

## Goal

Tell apart, every night and per source:

1. **the site is down / blocking us** (wait it out);
2. **our scraper is broken**, fully (exception) or **partially** (pagination
   stops early, a section or field selector dies) — needs a code fix;
3. **events were genuinely cancelled** (a few disappear while the rest is still
   there) — hide them.

Broken scrapers land in a queue (GitHub issues) that notifies the owner and can
be handed to Claude for a repair PR. Nothing is fully automatic: a human merges.

## Decisions (settled with the user)

- Queue + notifications = **GitHub issues** on `jpjagt/cartelita`.
- Cancelled events are **hidden, not deleted**, and un-hidden automatically if
  they reappear.
- **A null never overwrites a known value** in any upsert.
- jazzin.amsterdam gets a **content-derived external_id** (its maintainer
  re-scrapes everything nightly, so its ids are not stable).
- Thresholds below are starting values, kept as named constants in one module
  (`cartelera/health.py`).

## 1. Recording runs

New table `scrape_run` (one row per source per run): `id`, `source_slug`,
`started_at`, `finished_at`, `verdict` (`healthy | degraded | broken |
site_down`), `error_kind`, `error_message` (truncated traceback tail),
`metrics JSONB`, `acked BOOLEAN` (see §5). `metrics` holds source-level and
per-venue values:

- `emitted` — events the scraper returned;
- `known_upcoming` — the venue's visible events with `start_date >= today`
  (before this run);
- `reseen` — how many of those this run returned again (`coverage =
  reseen / known_upcoming`);
- `horizon_days` — `max(start_date) - today` of this run's events;
- `fill` — share of events with `price`, `start_time`, `description`.

Event columns (migration `0005`): `last_seen_at TIMESTAMPTZ` (stamped by every
upsert), `missed_runs INT NOT NULL DEFAULT 0`, `hidden_at TIMESTAMPTZ NULL`.

## 2. Verdicts

Evaluated after `scrape()` returns or raises, before writing.

**site_down** — the exception chain contains a transport-level failure:
`httpx.TransportError` (connect, DNS, timeout, protocol), an
`httpx.HTTPStatusError` with 5xx, or 403/429 (sub-kind `blocked`).

**broken** — any other exception (parsing, validation, `unknown category slug`,
whitelist violations), or `HTTPStatusError` 404/410 on a fetch (the listing URL
moved).

**degraded** — no exception, but the run is implausible against the source's
**baseline** = median of each metric over its last 14 *healthy-or-acked* runs
(only applied once ≥ 3 such runs exist). Any rule firing ⇒ degraded; evaluated
per venue for multi-venue sources (a venue with too few events for a floor is
skipped), and the source is degraded if any venue is (**superseded** for
multi-venue sources — see *Revision 2026-10-13* below: a venue-level rule now
degrades only that venue):

| Rule | Fires when | Floor (rule skipped below it) |
|---|---|---|
| empty | `emitted == 0` | baseline emitted ≥ 3 |
| count drop | `emitted < 0.5 × baseline emitted` | baseline emitted ≥ 10 |
| coverage drop | `coverage < 0.6` | `known_upcoming ≥ 10` |
| horizon shrink | `horizon_days < 0.5 × baseline horizon_days` | baseline horizon ≥ 14 days |
| field drop | `fill[f] < baseline fill[f] − 0.3` | baseline `fill[f] ≥ 0.5` |

Coverage catches early-stopping scrapers (pagination dies → later pages' known
events are not re-seen) even when the count looks plausible. A cancelled event
or two barely moves it.

**healthy** — none of the above.

## 3. What each verdict does to the data

| Verdict | Upsert | Miss counting / hiding |
|---|---|---|
| healthy | yes | yes |
| degraded | yes (new/changed events are real) | **no** |
| broken | **no** (transaction rolled back; last good data kept) | no |
| site_down | no | no |

**Null guard (all runs):** when updating an existing event, a field the scrape
returns as `None`/empty does not overwrite a stored non-null value (price,
times, description, image, language, recurrence hint, end date/time). A run can
change a value, never blank it.

## 4. Hiding cancelled events (reversible)

After a **healthy** run, per venue of the source:

- events returned by the run: `last_seen_at = now`, `missed_runs = 0`,
  `hidden_at = NULL` (an event that reappears is visible again);
- the venue's other events with `start_date >= today` and `hidden_at IS NULL`:
  `missed_runs += 1`; when it reaches **3**, `hidden_at = now`.

Past events are never touched. Web queries (`web/src/lib/queries.ts`) add
`AND e.hidden_at IS NULL`. Nothing is deleted.

## 5. Health state, issues and notification

Per source, derived from its recent `scrape_run`s: the current *bad streak*
(consecutive non-healthy runs, by verdict).

| Condition | Action |
|---|---|
| site_down streak ≥ 3 nights | open issue `site-down` |
| `blocked` streak ≥ 7 nights | (re)label as `broken` (needs a code change) |
| broken streak ≥ 2 | open issue `broken` |
| degraded streak ≥ 2 | open issue `degraded` |
| issue open + still bad | comment only when the verdict/error/rule changes, else at most weekly |
| first healthy run | comment "recovered", close the issue |

One open issue per source (title `scraper: <source_slug> — <kind>`, labels
`scraper-health` + `kind:<kind>`); the issue number is stored in a small
`source_health` table so later runs find it. GitHub sends the notification
(email/app). If `GITHUB_TOKEN`/`GITHUB_REPOSITORY` are unset (local dev), issue
actions are logged instead.

**Issue body** (everything a repair session needs): verdict + fired rules with
metrics vs baseline, error kind + traceback tail, last healthy run date, links
to the scraper module, its `<source>_SOURCE.md`, its test + fixture, the
`cartelera dry-run <module>` command, and a footer instructing a repairing agent
to follow `AGENTS.md` and the `writing-a-scraper` skill (re-verify against the
live site, refresh the fixture).

**Repair:** comment `@claude fix this` on the issue → the Claude GitHub Action
(`.github/workflows/claude.yml`, `anthropics/claude-code-action`) runs with the
repo checked out, so `AGENTS.md` + `.claude/skills/` apply, and opens a PR. The
human reviews/merges; the normal deploy follows. Needs the Claude GitHub app on
the repo and an `ANTHROPIC_API_KEY` (or OAuth token) repository secret — owner
setup, documented in `docs/deploy.md`. Alternatively open the issue in any
Claude Code session.

**Acknowledging a legitimate change** (a theatre's summer break):
`cartelera health ack <source>` marks the latest run `acked` (it then counts as
baseline), resets the streak and closes the issue with a comment.
`cartelera health` prints every source's state, streak, last healthy run and
open issue.

## 6. jazzin.amsterdam

`external_id = sha1(f"{start_date}T{HHMM|none}|{normalized casefold title}")[:16]`
(unique per venue per batch, guaranteed by the existing occurrence merge).
Rollout: the first run after deploy re-keys every jazzin event, so the old
numeric-id rows are not re-seen. Handled by a one-off
`cartelera health rekey jazzin-amsterdam` (dry-run by default) that, after a
successful new-key run, hides future jazzin events whose `external_id` is purely
numeric and acks the run so the coverage drop isn't flagged.

## 7. Where it runs

All inside `cartelera run` (the nightly Coolify task): scrape → classify →
write/hide → record `scrape_run` → update `source_health` → GitHub calls.
Exit code stays non-zero when any source is broken/site_down. The scraper
container needs `GITHUB_TOKEN` (fine-grained, Issues read/write on
`jpjagt/cartelita` only) and `GITHUB_REPOSITORY=jpjagt/cartelita`.

## 8. Testing

Unit: error classification table; each degraded rule incl. floors and
cold-start (< 3 baseline runs); per-venue evaluation for multi-venue sources;
null guard; miss counting / hiding / un-hiding, and that degraded/broken/
site_down runs never count misses; streak → issue transitions with a fake
GitHub client (open, comment-on-change, weekly cap, close on recovery, ack);
jazzin key stability across re-listed ids. Integration: `run` on a scratch DB
with a fake scraper simulating healthy → paginated-truncated → down → recovered.
Web: queries exclude hidden events.

## Revision 2026-10-13: venue-scoped verdicts for multi-venue sources

**Why.** On prod, jazzin.amsterdam (~190 venues, incl. discovered ones) was
`degraded` every run from 2026-10-12 because of single venues — De FilmHallen
and The Movies went to 0 events in jazzin's own feed (upstream breakage we
can't fix), plus `horizon_shrink` at cinema-the-pulse and meervaart. Any
venue-level rule degraded the whole source, so miss counting/hiding paused
for all its venues and a source issue (`#1 (degraded)`) opened.

**Verdicts.** The rules are evaluated exactly as before (§2), but:

- the **source verdict** comes from the `source`-scope rules only (plus
  exceptions → broken / site_down as before);
- a `venue:<slug>` rule marks only **that venue** degraded for the run.
  Recorded in `scrape_run.metrics`: `degraded_venues: [slug]` and a `verdict`
  per entry of `venues`. Readers derive degraded venues from the `fired`
  scopes, so runs recorded before this revision read correctly too.
- Single-venue sources are unchanged: they only have source-scope rules.

**Data (§3/§4).** After a source-healthy run, miss counting/hiding runs for
every venue **except** the ones degraded in this run (their events are
upserted, but neither missed nor hidden). A source-degraded run still pauses
hiding for the whole source.

**Baselines and coverage reference.** A run is *trusted for a venue* when it
wrote data and either the source was acked, the venue was acked in it
(below), or the run was source-healthy and the venue not degraded in it (a
venue absent from a run isn't degraded in it). Then:

- a venue's baseline = its metrics from the last 14 runs trusted for it
  (same `BASELINE_MIN_RUNS` and floors), so a degraded venue doesn't pollute
  its own baseline — otherwise after 14 source-healthy runs an empty venue
  would have an empty baseline, score healthy, and have its events hidden;
- a venue's coverage reference (the `last_seen_at >=` cut-off for its known
  events) = the newest run trusted for it. A healthy venue: the previous
  trusted run, as before. A venue degraded in the previous run falls back to
  its last trusted run's seen set, so a persistently truncated venue keeps
  being measured against its full view instead of its own truncated one
  (same reasoning as for sources in §2).
- The source baseline is unchanged (its source-healthy-or-acked runs).
- The lookback is the last `BASELINE_SCAN_RUNS` (60) runs that are healthy,
  acked or hold a venue ack; a venue degraded for longer than that falls back
  to a cold start (by then it has long been on the review issue).

**Issues.** Venue-level degradation never opens or keeps a source issue; the
source issue's signature only includes source-scope rules. A source issue
opened because of venue rules under the old semantics (prod `#1`) closes via
the normal recovery path — the next source-healthy run — and the close
comment says how many venues are still degraded and where they are tracked.
Instead:

- `cartelera health` shows per source the number of venues degraded in its
  latest run (minus acked ones); `cartelera health <source>` lists them with
  their fired rules and streak (consecutive runs that degraded the venue;
  broken/site_down runs neither count nor break it; a run where the venue was
  fine/absent, or a venue or source ack, ends it).
- Venues degraded for `VENUE_REVIEW_STREAK` (7)+ runs are listed on the
  source's rolling review issue (`venue-review`, the one for new discovered
  venues, now titled `<source>: venues to review`; any multi-venue source can
  get one): posted when the set of such venues or their rules changes, else
  at most weekly, and one "cleared" comment when none are left. If no review
  issue is open, one is opened. Bookkeeping: `source_health.
  venue_review_signature` / `venue_review_comment_at` (migration `0007`).

**Ack.** `cartelera health ack <source> <venue>` records the venue in the
latest data-writing run's `metrics.acked_venues`: that run becomes the
venue's coverage reference, its baseline **restarts** from that run (older
runs no longer count — so accepting "this venue has no programme any more"
actually sticks, unlike a source ack whose acked run is just one of 14), its
streak ends, and its visible upcoming events that run did not see are hidden
(reversible). The source issue and other venues are untouched.
`cartelera health ack <source>` is unchanged.

## Out of scope

Fully automatic repair/merge; a health web dashboard (the CLI + issues suffice);
alerting channels other than GitHub; per-field-level history beyond `fill`.
