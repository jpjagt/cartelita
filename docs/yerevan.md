## Genre taxonomy for Yerevan

Nine categories exist today. For Yerevan I'd carry six, drop two, add two or three.

| Slug        | Verdict                 | Reasoning                                                                                                                                                                          |
| ----------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `film`      | **core**                | Strong. A real arthouse house (Moscow Cinema, Europa Cinemas member) plus the Filmmakers' Union Cinema House, and Golden Apricot as the anchor festival.                            |
| `jazz`      | **core**                | The strongest single category. Two clubs run live jazz *seven nights a week* — that alone beats Barcelona's density.                                                                |
| `classical` | **core**                | Philharmonic + Chamber Music House + Conservatory + Opera. Same shape as Barcelona, with a Baroque organ hall as a bonus.                                                           |
| `theater`   | **core, with a caveat** | Deep repertoire, 20+ theatres. Almost all Armenian-language with no surtitles; one Russian-language house. See language note below.                                                 |
| `dance`     | **core, reframed**      | Contemporary dance is thin but real (Mihr, CoChoLab). The volume is ballet + folk. Needs a different filter than Barcelona's.                                                       |
| `club`      | **promote to core**     | Marginal in Barcelona. In Yerevan the techno scene is politically charged (Poligraf raid + forced closure) and entirely locally-made. Volatile, but the opposite of touristic.      |
| `kids`      | keep, low               | Puppet Theatre + Metro Theatre / National Centre of Aesthetics.                                                                                                                    |
| `flamenco`  | **drop**                | No local analogue. (Amusingly, Ulikhanyan does programme occasional flamenco nights — that's an `annotations` tag, not a category.)                                                 |
| `pop`       | **drop**                | Folds into the new `rock` bucket; everything else in it is the mainstream we're filtering out.                                                                                      |
| `folk`      | **new**                 | The flamenco analogue: duduk, Komitas repertoire, polyphony, folk dance. Sharp concert/tourist-show split — sharper than in Tbilisi, because the dinner-show industry here is huge. |
| `rock`      | **new**                 | Punk / metal / alt-indie. Real scene (Nemra, Altsight, rocker.am), small venue count, publishes almost exclusively to Instagram.                                                    |
| `art`       | **new, optional**       | Gallery openings, NPAK's alternative-art festival. Same flag as Tbilisi — doesn't fit the current data model (openings aren't ticketed occurrences).                                |

## Venue index

**Film**

| Venue                                        | Note                                                                                                                                                     | Confidence |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| Moscow Cinema (Kino Moskva)                  | **Start here.** 1936 constructivist house on Aznavour Sq, Europa Cinemas member, arthouse programming, four indoor halls + an **open-air hall**, and the Golden Apricot home venue. Also screens some mainstream — whitelist, like Balañá. | high       |
| Cinema House (Union of Film Professionals)   | The Filmoteca analogue: 500/120/80-seat halls, renovated 2018, retrospectives + festival hosting + a fireplace hall for post-screening talks.             | high       |
| Golden Apricot (festival, July)              | Not a venue but the year's anchor — 23rd edition July 2026. Programme spreads across Moscow Cinema and Cinema House.                                      | high       |
| Art House Film Gallery (AFG)                 | Mobile arthouse screening programme, no fixed address. Would need a social-media ingest path.                                                             | medium     |
| Filmadaran                                   | Film archive / preservation initiative. Screening frequency unverified.                                                                                  | low        |
| Naregatsi Art Institute                      | Mixed programme incl. documentary screenings alongside folk and classical.                                                                                | medium     |
| Nairi Cinema                                 | Historic house; verify whether current programming is arthouse or mainstream releases before including.                                                   | low        |
| Arten / Common Ground                        | Both run irregular film + documentary screenings as part of a broader programme. See Theater / cross-genre below.                                         | medium     |

Exclude: **Kinopark**, **Cinema Star** and the mall multiplexes (the Cavea analogue).

**Jazz** — the best-served category in the city.

| Venue                     | Note                                                                                                                                                        | Confidence |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| Malkhas Jazz Club         | The anchor. Founded by pianist Levon Malkhasyan, Pushkin St, **live music seven nights a week**, 21:00–02:00. The Jamboree analogue.                        | high       |
| Ulikhanyan Club           | 7 Sayat-Nova. Daily live music: jazz, fusion, funk, ethno-jazz, avant-garde folk. Has its own site *and* an Esora source page — likely the easiest scrape.  | high       |
| Mezzo Classic House Club  | Classical *and* jazz, plus blues/rock/folk. Multi-category venue → whitelist per list.                                                                       | high       |
| Calumet Ethnic Lounge Bar | World/ethnic live bands, Pushkin St. Genre-refusing in the Mutant Radio spirit; sits between `jazz`, `folk` and `rock`.                                     | medium     |
| Poplavok / Aragast        | The legacy jazz cafe by the Swan Lake pond. Borderline — check whether it's still real programming or dinner-with-jazz for visitors.                        | low        |

**Classical**

| Venue                                          | Note                                                                                                                                     | Confidence |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ---------- |
| Komitas Chamber Music House                    | **Best single pick.** 300 seats, Circular Park, and a 4,000-pipe Dutch Baroque organ installed 1979. The Palau analogue at Ateneu scale. | high       |
| Aram Khachaturian Concert Hall / Philharmonic  | 1,276 seats, home of the Armenian National Philharmonic — but also books mainstream pop. **Whitelist required.**                          | high       |
| Komitas State Conservatory                     | Student and faculty concerts, high volume, low ticket price. Verify whether dates are published anywhere but Facebook.                    | medium     |
| Opera & Ballet Theatre (Spendiaryan)           | Liceu analogue: opera + ballet + folk galas + duduk evenings. Whitelist.                                                                  | high       |
| Arno Babajanyan Concert Hall                   | Mid-size mixed house. Verify programming split.                                                                                          | medium     |
| Naregatsi Art Institute                        | Chamber concerts, folk, and the winter home of the Karin dance nights. Genuinely cross-genre.                                             | medium     |

**Theater** — the deepest category, and the one with the same structural problem as Tbilisi.

| Venue                                      | Note                                                                                                                                                       |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Yerevan State Pantomime Theatre**        | **Best single pick.** Non-verbal repertoire — zero language barrier. The Movement Theatre analogue exactly.                                                 |
| Sundukyan State Academic Theatre           | The national flagship, founded 1922. Classical + Brecht/Chekhov/Camus repertoire.                                                                          |
| Stanislavski Russian Theatre               | Russian-language, 1937, Abovyan St. Include or not depending on which audience you're serving — see language note.                                          |
| Hamazgayin Theatre (Sos Sargsyan)          | Founded 1991 by Sos Sargsyan. Serious mid-size house.                                                                                                      |
| **Arten**                                  | Independent chamber theatre, founded late 2022 by a relocated artistic director. Performances, **open rehearsals**, lectures, film screenings, kids' events. The Antic Teatre analogue and the most Cartelita-spirited venue in the city. |
| Goy Theatre                                | "National Experimental Centre of Performing Arts", est. 1988. Verify current activity.                                                                     |
| Xronotope / Chronotope                     | Founded in St Petersburg 2021, re-based in Yerevan, now producing in Armenian. Three productions so far.                                                    |
| Boheme Theatre                             | Est. 2016, 320 seats, in the Writers' Union building. One of the youngest houses.                                                                          |
| Metro Theatre (National Centre of Aesthetics) | Est. 1992. Also the main `kids` venue alongside the Puppet Theatre.                                                                                     |
| Tech Tegh                                  | Independent productions, from the Ars Techne index. Low volume, verify.                                                                                    |
| Yerevan State Puppet Theatre (Tumanyan)    | `kids`. The Gabriadze slot, minus the world-fame.                                                                                                          |
| HIGH FEST (festival, October)               | International performing-arts festival since 2003 — theatre, contemporary dance, movement. The one week a year the whole category is legible at once.       |

**Club / electronic**

| Venue          | Note                                                                                                                                                                                         |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hayfilm Cluster | Former Armenfilm studio on Ashtarak Highway, ~1,500 cap, multi-room techno / breakbeat / acid / experimental. Also functions as cinema and event space. The current centre of gravity.       |
| Club 12        | Small, intimate raves, local and rising Armenian DJs. Verify it's still open.                                                                                                                |
| Cyber Folk     | Not a venue — a DJ/production school founded out of Poligraf's closure, explicitly trying to move electronic music beyond hedonism. Runs events; worth following for where the scene resurfaces. |
| ~~Poligraf~~   | **Closed January 2024** after a violent police raid (April 2023) and a long legal fight. Kept here as context: this category is politically exposed, not just commercially fragile.           |

⚠️ **This category churns harder than anything in Barcelona.** Poligraf and The Office both gone. Expect to revalidate every few months, and expect a lot of one-off parties announced only on Instagram.

**Rock / punk / alt**

| Venue           | Note                                                                                                             |
| --------------- | ------------------------------------------------------------------------------------------------------------------ |
| Tonelab Studio  | Independent venue *and* promoter — intimate club shows, underground rock/metal/punk, local bands, residencies.   |
| Kami Club       | Abovyan St, live bands most nights, rock and blues, ~5,000 AMD door.                                              |
| Stop Club       | 37 Moskovyan. Rock, contemporary, neo and ethnic music; young local crowd.                                        |
| rocker.am       | Not a venue — the Armenian rock/metal portal. Probably the best single source for finding gigs in this category.  |

**Folk / traditional**

| Venue                                            | Note                                                                                                                                                                                                                                                                          |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **"Karin" — *We and Our Dances*, last Friday monthly** | **Free, open-air at the Cascade (May–Sep), indoors at Naregatsi Art Institute (Oct–Apr).** Open folk-dance lesson where strangers teach each other. This is the single most manifesto-aligned event in either city: free, drop-in, and structurally impossible to attend "wrong" alone. |
| Yerevan Duduk Festival (October)                 | A series of **free** duduk concerts across the city.                                                                                                                                                                                                                          |
| Opera House / Philharmonic / Naregatsi           | Where the serious ensembles (Shoghaken and peers) actually perform, alongside their classical programming.                                                                                                                                                                     |
| Churches (Katoghike, Zoravor, St Gregory)        | Sacred chant during liturgy — unticketed, recurring, free. Same data-model edge case as Anchiskhati in Tbilisi, worth solving for the same reason.                                                                                                                             |

Exclude: the **Cascade-adjacent and Northern Avenue duduk-with-dinner restaurants** — nightly folk shows priced for tour groups. Textbook fails-the-classifier, and there are far more of them here than in Tbilisi.

**Contemporary dance**

| Venue           | Note                                                                                                          |
| --------------- | --------------------------------------------------------------------------------------------------------------- |
| Mihr Theatre    | Armenia's first contemporary dance company (2003, Mlke-Galstyan siblings). Site-specific, physical, open-air. |
| CoChoLab Armenia | Choreography lab from the Ars Techne index.                                                                   |
| HIGH FEST       | See Theater — the annual concentration point for this category.                                               |

**Art / exhibitions** *(optional category, doesn't fit the model yet)*

NPAK / ACCEA is the flagship — its "Wild Children" alternative-art festival hit its 30th edition in spring 2026, after a hiatus following co-founder Edward Balassanian's death in 2024. Beyond it, Ars Techne maintains a field-researched index of ~70 independent, artist-run and experimental spaces in Yerevan (Mirzoyan Library, Latitude, Rambalkoshe, 4 Plus, Bookstore No. 4, Working Class Coffee…). That index is the best curation shortlist available for the whole alternative scene, not just visual art — worth reading in full before finalising any venue list.

## Four things that differ structurally from Barcelona

**1. Scraping architecture — better than Tbilisi, worse than Barcelona.** Yerevan has real aggregators. `tomsarkgh.am` carries ~1,700 upcoming events across ~1,900 venues with English support, and its taxonomy maps almost 1:1 onto ours: Cinema / Concert (Rock, Jazz, Classical, Dance) / Theater / Opera & Ballet / Clubs & pubs. `esora.app` is even more useful structurally — it exposes a **page per source venue**, which is exactly the shape a whitelist-filtered aggregator scraper wants. Others: `toms.am`, `ticket-am.com`, `eventix.am`, and `kinoafisha.info` for cinema showtimes.

The strategy this implies is different from Barcelona's 45 one-per-venue scrapers: **a small number of aggregator scrapers filtered by a curated venue whitelist**. The upside is that most of the classical/theatre/opera volume arrives from two or three scrapers. The catch is that an aggregator's *category* is not our *curation* — tomsarkgh's "Concert" bucket contains stadium pop and Karen Demirchyan Complex shows. The venue whitelist still does all the editorial work; the aggregator just moves bytes.

What the aggregators do **not** cover is the part we most want: Tonelab, Hayfilm parties, Karin's dance nights, Arten's open rehearsals, most of the rock scene. Those live on Instagram and Facebook. Same conclusion as Tbilisi — a social ingest path is the gating piece of work, and it should be scoped before the venue list is frozen.

**2. Language is a three-way split, not a two-way one.** Armenian is the working language of nearly all theatre, and it's a **non-Latin script**, which the current `ca`/`es`/`en` i18n has never had to handle (slugs, sorting, fonts, transliteration for URLs). Russian is a genuine second audience — the Stanislavski Theatre programmes in it, Arten and Xronotope came out of the 2022 relocation wave, and a large Russian-speaking population lives here now. English is the visitor/expat layer. The `EventTranslation` model already supports all of this; the decision that actually matters is editorial: **canonical `hy` with `ru`/`en` translations**, and accepting that some venues will only ever publish in one of them. The Pantomime Theatre is the one venue that sidesteps the question entirely.

**3. The touristic classifier needs recalibrating in the opposite direction from Tbilisi.** In Tbilisi the trap was assuming that internationally famous = touristic. In Yerevan the trap is volume: the city has a large, well-oiled *folk-show-with-dinner* industry, and it will flood any `folk` category you open. Meanwhile a 1,500-capacity rave in a Soviet film factory has almost no foreign profile and is entirely local. Same test as Tbilisi, and it works here too: **is the programming made for the people who live here?** Applied to the two hard cases — Moscow Cinema hosts a festival that draws the international press but programmes for Yerevan year-round (include); Poplavok has no foreign profile at all but may exist to sell dinner (verify in person).

**4. Political fragility is a first-class risk here.** Poligraf wasn't outcompeted, it was raided and litigated out of existence. NPAK went dark for eighteen months after a founder died. Neither is a normal venue-churn story, and neither would be predicted by scraping. Whatever the revalidation cadence is for Barcelona, halve it — and treat a venue going quiet as a signal to check the news, not just the site.

## Where I'd start

Seven venues, covering five genres, all with real weekly volume:

**Moscow Cinema** (film, whitelist) · **Cinema House** (film) · **Malkhas** (jazz) · **Ulikhanyan** (jazz) · **Komitas Chamber Music House** (classical) · **Pantomime Theatre** (theater, no language barrier) · **Arten** (theater + cross-genre)

Then the one thing that has no Barcelona analogue at all: **Karin's *We and Our Dances*** — free, monthly, drop-in, and the clearest expression of what the manifesto says the product is for. It's a single recurring event rather than a venue feed, so it's cheap to add and disproportionately worth having.

Add **Tonelab**, **Hayfilm** and **rocker.am** as soon as there's a social-media ingest path, since no listings service will cover them properly.

Build order suggestion: one aggregator scraper (`esora.app`, because of its per-source pages) filtered to the whitelist above, rather than seven venue scrapers. That's a different first task than Barcelona had, and it's worth prototyping before committing to the venue list.

Confidence caveat: this is built from web research, not fieldwork. I verified that Moscow Cinema is a Europa Cinemas member with an open-air hall, that Malkhas and Ulikhanyan both run nightly programmes, that Poligraf closed in January 2024, and that the Karin dance nights run monthly at the Cascade/Naregatsi. I did **not** verify scrapeability for any venue — `khachaturianhall.am` and `moscowcinema.com` both resisted a plain fetch (JS-rendered and 403 respectively), which is itself a signal that browser-based scraping will be needed more often than in Barcelona. Several smaller entries (Nairi, Poplavok, Goy, Tech Tegh, Club 12) rest on single sources and should be verified before inclusion.

Sources: [Moscow Cinema](https://en.wikipedia.org/wiki/Moscow_Cinema), [Cinema House / European Film Academy](https://www.europeanfilmacademy.org/activity/armenia-house-of-cinema-yerevan/), [Golden Apricot](https://filmfreeway.com/GoldenApricotYerevanInternationalFilmFestival), [Malkhas Jazz Club](https://www.armenia-spirit.com/guides/malkhas-jazz-club-yerevan/), [Ulikhanyan Club](https://ulikhanyanclub.com/en), [Mezzo](http://mezzo.am/), [Komitas Chamber Music House](https://en.wikipedia.org/wiki/Komitas_Chamber_Music_House), [Aram Khachaturian Concert Hall](https://khachaturianhall.am/en/), [List of theaters in Yerevan](https://en.wikipedia.org/wiki/List_of_theaters_in_Yerevan), [Arten](https://www.arten.theater/en), [Boheme](https://boheme-theater.am/en), [Chronotope](https://artfocusnow.com/discoveries/found-in-translation-chronotope-theatre-company-re-invents-itself-in-yerevan/), [Mihr Theatre](https://mihrtheatre.com/), [HIGH FEST](https://highfest.am/about-us/), [ACCEA/NPAK](https://www.accea.info/about-us/), [Poligraf closure](https://djmag.com/news/yerevan-club-poligraf-announces-permanent-closure-amid-legal-battles-authorities), [Poligraf raid](https://www.dazeddigital.com/music/article/59754/1/poligraf-armenian-nightclub-brutally-raided-by-police), [Cyber Folk](https://djmag.com/features/meet-dj-and-production-school-reshaping-armenias-electronic-music-scene), [Hayfilm Cluster](https://esora.app/en/yerevan/sources/12e0eff5-e2d6-4654-9fb7-d89b0e758476), [Yerevan live music directory](https://armeniainfo.ai/blog/yerevan-nightlife/best-live-music-venues-in-yerevan-your-full-directory-to-the-citys-vibrant-soundscape), [Karin folk dance nights](https://www.likealocalguide.com/yerevan/we-and-our-dances-dance-event), [Karin ensemble](https://karinfolk.am/?lang=en), [Yerevan Duduk Festival](https://musicofarmenia.com/portfolio/yerevan-duduk-festival/), [Ars Techne independent spaces index](https://arstechne.net/independent-spaces-yerevan), [tomsarkgh.am](https://www.tomsarkgh.am/en), [Esora](https://esora.app/en/yerevan), [rocker.am](https://rocker.am/)
