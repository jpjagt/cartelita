from __future__ import annotations
import datetime as dt
import hashlib
import logging
import re
import unicodedata
from collections import Counter

import httpx

from cartelera.scrapers import register_source
from cartelera.types import (
    ScrapedEvent,
    VenueDefinition,
    ListMembership,
    SourceDefinition,
)

# jazzin.amsterdam — curated Amsterdam culture calendars (jazz, classical,
# theater, pop, club, film, alternative; ~6,200 upcoming events across ~190
# venues) with a
# public JSON API. MULTI-VENUE, OPT-OUT source (see jazzin_amsterdam_SOURCE.md):
# every venue the feed names becomes a venue automatically (discovered at run
# time, see cartelera.discovery); code holds only the exceptions — VENUES
# (overrides: merges, names, addresses, categories) and DENIED (names that are
# never venues). The API returns at most PAGE_SIZE events per call; `offset`
# pages (its `page` param is ignored).
API_URL = "https://jazzin.amsterdam/api"
PAGE_SIZE = 600
MAX_PAGES = 20  # safety stop against a misbehaving offset
SOURCE_SLUG = "jazzin-amsterdam"
CITY_SLUG = "amsterdam"
FALLBACK_URL = "https://jazzin.amsterdam/"

# jazzin calendar id → our category slug; the calendar IS the discriminator.
# `alternativeAmsterdam` (the site's "independent" tab: squats and DIY spaces —
# gigs, vokus, workshops, assemblies) → alternative. Not used: `movieAmsterdam`
# (Pathé multiplexes, ~200 screenings/day, 3 days ahead).
CALENDARS: dict[str, str] = {
    "jazzAmsterdam": "jazz",
    "classicalAmsterdam": "classical",
    "theaterAmsterdam": "theater",
    "popAmsterdam": "pop",
    "clubAmsterdam": "club",
    "filmAmsterdam": "film",
    "alternativeAmsterdam": "alternative",
}

logger = logging.getLogger(__name__)

# OVERRIDES: (venue slug, display name, address, jazzin venue-name aliases,
# categories). jazzin's `venue` field is free text typed per upstream source,
# so one venue arrives under several spellings ("ZOJazz Stage", "ZOjazz
# Stage", "ZOJazzstage "); aliases are matched after _venue_key normalization
# (case/whitespace-insensitive, nothing fuzzier) and merge those names into
# one venue. `categories` are the calendars the venue appears in: each becomes
# a whitelisted list membership; for these venues the table is authoritative
# (seeded; a new calendar is logged, not added). Addresses are jazzin's; the
# ones it gives only as "Amsterdam" are hand-filled or None. A name in no row
# and not DENIED is a discovered venue (see discover_venues); add a row only
# to merge spellings or to override what discovery would derive.
VENUES: list[tuple[str, str, str | None, list[str], list[str]]] = [
    ('concertgebouw', 'Het Concertgebouw', 'Concertgebouwplein 10, 1071 LN Amsterdam',
     ['Het Concertgebouw', 'Concertgebouw'], ['jazz', 'classical']),
    ('lab111', 'LAB111', 'Arie Biemondstraat 111, 1054 PD Amsterdam',
     ['LAB111'], ['film']),
    ('melkweg', 'Melkweg', 'Lijnbaansgracht 234A, 1017 PH Amsterdam',
     ['Melkweg'], ['jazz', 'pop', 'club']),
    ('eye-filmmuseum', 'Eye Filmmuseum', 'IJpromenade 1, 1031 KT Amsterdam',
     ['Eye Filmmuseum'], ['film']),
    ('muziekgebouw', "Muziekgebouw aan 't IJ", 'Piet Heinkade 1, 1019 BR Amsterdam',
     ['Muziekgebouw', "Muziekgebouw aan 't IJ"], ['jazz', 'classical']),
    ('carre', 'Koninklijk Theater Carré', 'Amstel 115-125, 1018 EM Amsterdam',
     ['Carré'], ['jazz', 'theater']),
    ('mezrab', 'Mezrab', 'Veemkade 576, 1019 BL Amsterdam',
     ['Mezrab'], ['theater']),
    ('de-kleine-komedie', 'De Kleine Komedie', 'Amstel 56-58, 1017AC Amsterdam',
     ['De Kleine Komedie'], ['theater']),
    ('theater-de-landing', 'Theater De Landing', 'Uilenstede 106, 1183 AM Amstelveen',
     ['Theater De Landing'], ['theater']),
    ('bimhuis', 'Bimhuis', 'Piet Heinkade 3, 1019 BR Amsterdam',
     ['Bimhuis'], ['jazz']),
    ('cinema-the-pulse', 'Cinema The Pulse', 'Hildegard von Bingenstraat 4, 1081 LH Amsterdam',
     ['Cinema The Pulse'], ['film']),
    ('theater-mascini', 'Theater Mascini', 'Zeedijk 24a, 1012 AZ Amsterdam',
     ['Theater Mascini'], ['jazz', 'theater']),
    ('splendor', 'Splendor', 'Nieuwe Uilenburgerstraat 116, 1011 LX Amsterdam',
     ['Splendor'], ['jazz', 'classical']),
    ('theater-de-griffioen', 'Theater de Griffioen', 'De Boelelaan 1111, 1081 HV Amsterdam',
     ['Theater de Griffioen'], ['jazz', 'theater']),
    ('podium-mozaiek', 'Podium Mozaïek', 'Bos en Lommerweg 191, 1055 DT Amsterdam',
     ['Podium Mozaïek'], ['classical', 'theater']),
    ('theater-de-omval', 'Theater de Omval (Diemen)', 'Ouddiemerlaan 104, 1111 HL Diemen',
     ['Theater de Omval'], ['jazz', 'theater']),
    ('t-zonnehuis', "'t Zonnehuis", 'Zonneplein 30, 1033 EK Amsterdam',
     ["'t Zonnehuis", 'Zonnehuis'], ['jazz', 'classical', 'theater', 'pop']),
    ('theater-bellevue', 'Theater Bellevue', 'Leidsekade 90, 1017 PN Amsterdam',
     ['Theater Bellevue'], ['theater']),
    ('studio-k', 'Studio/K', 'Timorplein 62, 1094 CC Amsterdam',
     ['Studio/K'], ['film', 'alternative']),
    ('meervaart', 'Meervaart', 'Meer en Vaart 300, 1068 LE Amsterdam',
     ['Meervaart Theater'], ['jazz', 'theater']),
    ('kriterion', 'Kriterion', 'Roetersstraat 170, 1018 WE, Amsterdam',
     ['Kriterion'], ['film']),
    ('delamar', 'DeLaMar Theater', 'Marnixstraat 402, Amsterdam',
     ['DeLaMar Theater', 'Café DeLaMar'], ['theater']),
    ('de-uitkijk', 'De Uitkijk', 'Prinsengracht 452, 1017 KE Amsterdam',
     ['De Uitkijk'], ['film']),
    ('escape', 'Escape', 'Rembrandtplein 11, 1017 CT Amsterdam',
     ['Escape'], ['club']),
    ('cinema-de-vlugt', 'Cinema de Vlugt', 'Burgemeester de Vlugtlaan 125, 1063 BJ Amsterdam',
     ['Cinema de Vlugt'], ['film']),
    ('polanentheater', 'Polanentheater', 'Polanenstraat 174, 1013 WC, Amsterdam',
     ['Polanentheater'], ['theater']),
    ('ziggo-dome', 'Ziggo Dome', 'De Passage 100, 1101 AX Amsterdam',
     ['Ziggo Dome'], ['pop']),
    ('john-doe', 'John Doe', 'Rembrandtplein 31, 1017 CT Amsterdam, Netherlands',
     ['John Doe'], ['club']),
    ('de-roode-bioscoop', 'De Roode Bioscoop', 'Haarlemmerplein 7, 1013 HP Amsterdam',
     ['De Roode Bioscoop', 'Roode Bioscoop'], ['jazz', 'classical', 'theater']),
    ('theater-vrijburcht', 'Theater Vrijburcht', 'Jan Olphert Vaillantlaan 143, 1086 XZ Amsterdam',
     ['Theater Vrijburcht'], ['jazz', 'theater']),
    ('black-cat-theatre', 'Black Cat Theatre', 'Schakelstraat 2, 1014 AW Amsterdam',
     ['Black Cat Theatre'], ['theater']),
    ('cafe-de-pianist', 'Café de Pianist', 'Groen van Prinstererstraat 41, 1051 EH Amsterdam',
     ['Café de Pianist'], ['jazz']),
    ('de-duif', 'De Duif', 'Prinsengracht 756, 1017 LD Amsterdam',
     ['De Duif'], ['jazz', 'classical', 'pop']),
    ('zojazz-stage', 'ZOJazz Stage', 'Bijlmerplein 888, 1102 MG Amsterdam-Zuidoost',
     ['ZOJazz Stage', 'ZOJazzstage', 'Concertzaal'], ['jazz']),
    ('plein-theater', 'Plein Theater', 'Sajetplein 39, 1091 DB Amsterdam',
     ['Plein Theater'], ['theater']),
    ('de-waalse-kerk', 'De Waalse Kerk', 'Walenpleintje 157-159, 1012 JZ Amsterdam',
     ['De Waalse Kerk'], ['classical']),
    ('oosterkerk', 'Oosterkerk', 'Kleine Wittenburgerstraat 3, 1018 LS Amsterdam',
     ['Oosterkerk'], ['classical', 'theater']),
    ('conservatorium-van-amsterdam', 'Conservatorium van Amsterdam', 'Oosterdokskade 151, 1011 DL Amsterdam',
     ['CvA', 'Amsterdam Blue Dock, CvA', 'Bernard Haitinkzaal, CvA', 'Sweelinckzaal, CvA',
      'Ensemblezaal, CvA'], ['jazz', 'classical', 'pop']),
    ('cafe-de-engelbewaarder', 'Café de Engelbewaarder', 'Kloveniersburgwal 59HS, 1011 JZ Amsterdam',
     ['Café de Engelbewaarder'], ['jazz']),
    ('theater-de-krakeling', 'Theater De Krakeling', 'Pazzanistraat 15, 1014 DB Amsterdam',
     ['Theater De Krakeling'], ['theater']),
    ('orgelpark', 'Orgelpark', 'Gerard Brandtstraat 28, 1054 JK Amsterdam',
     ['Orgelpark'], ['classical']),
    ('theater-de-richel', 'Theater De Richel', 'Nieuwezijds Voorburgwal 282, 1012 RT Amsterdam',
     ['Theater De Richel'], ['jazz', 'theater']),
    ('english-reformed-church', 'English Reformed Church', 'Begijnhof 48, 1012 WV Amsterdam',
     ['English Reformed Church'], ['classical']),
    ('westweelde', 'WestWeelde', 'Klönneplein 4, 1014 DD Amsterdam',
     ['WestWeelde'], ['club']),
    ('amstelkerk', 'Amstelkerk', 'Amstelveld 10, 1017 JD Amsterdam',
     ['Amstelkerk'], ['classical']),
    ('skatecafe-karin-yvonne', 'Skatecafe Karin & Yvonne', 'Gedempt Hamerkanaal 42, 1021 KM, Amsterdam',
     ['Skatecafe Karin & Yvonne'], ['club']),
    ('chicago-social-club', 'Chicago Social Club', 'Leidseplein 12, 1017 PT Amsterdam',
     ['Chicago Social Club'], ['club']),
    ('van-houtenkerk', 'Van Houtenkerk (Weesp)', None,
     ['Van Houtenkerk'], ['classical']),
    ('tolhuistuin', 'Tolhuistuin', 'IJpromenade 2, 1031 KT Amsterdam',
     ['Tolhuistuin'], ['jazz', 'theater', 'pop', 'alternative']),
    ('posthoornkerk', 'Posthoornkerk', 'Haarlemmerstraat 124, 1013 EX Amsterdam',
     ['Posthoornkerk'], ['jazz', 'classical']),
    ('de-filmhallen', 'De FilmHallen', 'Hannie Dankbaarpassage 12, 1053 RT Amsterdam',
     ['De FilmHallen'], ['film']),
    ('de-khl', 'De KHL', 'Oostelijke Handelskade 44, 1019 BM Amsterdam',
     ['De KHL'], ['jazz', 'theater']),
    ('q-factory', 'Q-Factory', 'Atlantisplein 1, 1093 NE, Amsterdam',
     ['Q-Factory'], ['pop']),
    ('thuishaven', 'Thuishaven', 'Contactweg 68, 1014 BW, Amsterdam',
     ['Thuishaven'], ['club']),
    ('contra', 'Contra', 'Oudezijds Achterburgwal 235, 1012 DL Amsterdam',
     ['Contra'], ['jazz']),
    ('paradiso', 'Paradiso', 'Weteringschans 6-8, 1017 SG Amsterdam',
     ['Paradiso'], ['jazz', 'pop']),
    ('dominicuskerk', 'Dominicuskerk', 'Spuistraat 12A, 1012 TS Amsterdam',
     ['Dominicuskerk'], ['classical']),
    ('de-sloot', 'De Sloot', 'Rhoneweg 6-10, 1043 AH Amsterdam',
     ['De Sloot'], ['theater']),
    ('schouwburg-amstelveen', 'Schouwburg Amstelveen', 'Uilenstede 106, 1183 AM Amstelveen',
     ['Schouwburg Amstelveen'], ['theater']),
    ('club-up', 'Club Up', 'Korte Leidsedwarsstraat 26-1, Amsterdam, Nederland',
     ['Club Up'], ['club']),
    ('zaal-100', 'Zaal 100', 'De Wittenstraat 100, 1052 BA Amsterdam',
     ['Zaal 100'], ['jazz', 'alternative']),
    ('kompaszaal', 'Kompaszaal', 'KNSM-Laan 311, 1019 LE Amsterdam',
     ['Kompaszaal'], ['jazz']),
    ('the-waterhole', 'The Waterhole', 'Korte Leidsedwarsstraat 49, 1017 PW Amsterdam',
     ['The Waterhole'], ['pop']),
    ('lofi', 'Lofi', 'Basisweg 63, 1043 AN, Amsterdam',
     ['Lofi'], ['club']),
    ('het-ketelhuis', 'Het Ketelhuis', 'Westergas, Pazzanistraat 4, Amsterdam',
     ['Het Ketelhuis'], ['film']),
    ('maloe-melo', 'Maloe Melo', 'Lijnbaansgracht 163, Amsterdam, Noordholland, Nederland',
     ['Maloe Melo'], ['pop']),
    ('chin-chin-club', 'Chin Chin Club', 'Rozengracht 133, 1016 LV, Amsterdam',
     ['Chin Chin Club'], ['club']),
    ('bret', 'BRET', 'Orlyplein 76, 1043 DP, Amsterdam',
     ['BRET'], ['club']),
    ('radio-radio', 'Radio Radio', 'Pazzanistraat 3, 1014 DB Amsterdam',
     ['Radio Radio'], ['club']),
    ('nachbar', 'nachbar', 'Nieuwezijds Voorburgwal 169a',
     ['nachbar'], ['club']),
    ('club-dauphine', 'Club Dauphine', 'Prins Bernhardplein 175, 1097 BL Amsterdam',
     ['Club Dauphine'], ['pop']),
    ('cafe-czaar', 'Café Czaar', 'Czaar Peterstraat 281, 1018 PL Amsterdam',
     ['Café Czaar'], ['jazz']),
    ('pianola-museum', 'Pianola Museum', 'Westerstraat 106, 1015 MN Amsterdam',
     ['Pianola Museum', 'Gelvinck Pianola Museum'], ['jazz', 'classical']),
    ('de-kleine-kerk', 'De Kleine Kerk (Duivendrecht)', 'Rijksstraatweg 129, Duivendrecht, Netherlands',
     ['De Kleine Kerk'], ['classical']),
    ('tillatec', 'TILLATEC', 'Doctor Jan van Breemenstraat 1; 1056 AB Amsterdam',
     ['TILLATEC'], ['club']),
    ('buiksloterkerk', 'Buiksloterkerk', 'Buiksloterkerkpad 10, 1034 VZ Amsterdam',
     ['Buiksloterkerk'], ['classical']),
    ('nedpho-koepel', 'NedPhO-Koepel', 'Batjanstraat 3, 1094 RB Amsterdam',
     ['NedPhO-Koepel'], ['classical']),
    ('perdu', 'Perdu', 'Kloveniersburgwal 86, 1012 CZ Amsterdam',
     ['Perdu'], ['theater']),
    ('garage-noord', 'Garage Noord', 'Gedempt Hamerkanaal 40 1021KM, Amsterdam',
     ['Garage Noord'], ['club']),
    ('crea', 'CREA', 'Nieuwe Achtergracht 170, 1018 WV Amsterdam',
     ['CREA'], ['jazz']),
    ('cafe-parisius', 'Café Parisius', 'Borneostraat 112, Amsterdam',
     ['Café Parisius'], ['jazz']),
    ('kamermuziek-in-de-koningszaal', 'Kamermuziek in de Koningszaal', 'Plantage Middenlaan 41-A, 1018 DC  Amsterdam',
     ['Kamermuziek in de Koningszaal'], ['classical']),
    ('schuilkerk-de-hoop', 'Schuilkerk De Hoop', None,
     ['Schuilkerk De Hoop'], ['classical', 'theater']),
    ('pianobar-maxim', 'Pianobar Maxim', 'Leidsekruisstraat 33, 1017 RG Amsterdam',
     ['Pianobar Maxim'], ['pop']),
    ('doka', 'Doka', 'Wibautstraat 150, 1091 GR Amsterdam',
     ['Doka'], ['club']),
    ('parallel', 'Parallel', 'Buiksloterweg 5C, 1031 CC Amsterdam',
     ['Parallel'], ['club']),
    ('the-movies', 'The Movies', 'Haarlemmerdijk 161, Amsterdam',
     ['The Movies'], ['film']),
    ('plofhuis7', 'Plofhuis7 (Weesp)', 'Uitermeer 3, 1381 HP Weesp',
     ['Plofhuis7 (Weesp)'], ['jazz', 'classical']),
    ('seinwezen', 'Seinwezen', None,
     ['Seinwezen'], ['classical']),
    ('midwest', 'Midwest', 'Cabralstraat 1, 1057 CD Amsterdam',
     ['Midwest'], ['theater', 'pop', 'alternative']),
    ('bitterzoet', 'Bitterzoet', 'Spuistraat 2, 1012 TS Amsterdam',
     ['Bitterzoet'], ['pop', 'club']),
    ('toekomstmuziek', 'Toekomstmuziek', 'Danzigerbocht 29, 1013 AM, Amsterdam',
     ['Toekomstmuziek'], ['club']),
    ('murmur', 'murmur', 'Asterweg 6, 1031 HN, Amsterdam',
     ['murmur'], ['club']),
    ('huis-de-pinto', 'Huis de Pinto', 'St. Antoniesbreestraat 69, 1011 HB Amsterdam',
     ['Huis de Pinto'], ['jazz', 'classical']),
    ('theater-de-dillewijn', 'Theater De Dillewijn (Ankeveen)', 'Stichts End 57, 1244 PL Ankeveen',
     ['Theater De Dillewijn (Ankeveen)'], ['jazz']),
    ('torpedo-theater', 'Torpedo Theater', 'Sint Pieterspoortsteeg 33, 1012 HM Amsterdam',
     ['Torpedo Theater'], ['classical', 'theater']),
    ('tobacco-theater', 'TOBACCO Theater', 'Nes 75-87, 1012 KD Amsterdam',
     ['TOBACCO Theater'], ['theater']),
    ('apollofirst-theater', 'Apollofirst theater', 'Apollolaan 123, 1077 AP, Amsterdam',
     ['Apollofirst theater'], ['theater']),
    ('the-cave', 'The Cave', 'Prinsengracht 472 sous, 1017 KG  Amsterdam',
     ['The Cave'], ['pop']),
    ('akhnaton', 'Akhnaton', 'Nieuwezijds Kolk 25, 1012 PV Amsterdam',
     ['Akhnaton'], ['club']),
    ('warehouse-elementenstraat', 'Warehouse Elementenstraat', 'Elementenstraat 25, 1014 AR, Amsterdam',
     ['Warehouse Elementenstraat'], ['club']),
    ('de-nieuwe-anita', 'De Nieuwe Anita', 'Frederik Hendrikstraat 111, 1052 HN Amsterdam',
     ['De Nieuwe Anita'], ['jazz', 'alternative']),
    ('salon-de-ijzerstaven', 'Salon de IJzerstaven', 'Bickersgracht 10, 1013 LE Amsterdam',
     ['Salon de IJzerstaven'], ['jazz', 'classical']),
    ('de-roode-remise', 'De Roode Remise', 'Haarlemmerplein 11, 1013 HP Amsterdam',
     ['De Roode Remise'], ['jazz', 'classical', 'alternative']),
    ('de-ceuvel', 'De Ceuvel', 'Korte Papaverweg 2, 1032 KB Amsterdam',
     ['De Ceuvel'], ['pop', 'alternative']),
    ('panama', 'Panama', 'Oostelijke Handelskade 4, 1019 BM Amsterdam',
     ['Panama'], ['club']),
    ('occii', 'OCCII', 'Amstelveenseweg 134, 1075 XL Amsterdam',
     ['OCCII'], ['jazz', 'alternative']),
    ('pinksterkerk', 'Pinksterkerk', None,
     ['Pinksterkerk'], ['classical', 'theater']),
    ('rozengracht-55h', 'Rozengracht 55H', 'Rozengracht 55H, Amsterdam',
     ['Rozengracht 55H'], ['classical']),
    ('de-thomas', 'De Thomas', 'Prinses Irenestraat 36, 1077 WX Amsterdam',
     ['De Thomas'], ['classical']),
    ('borisov', 'Borisov', 'Rigakade 10 1013 BC Amsterdam, Netherlands',
     ['Borisov'], ['club']),
    ('walhalla-brouwerij-proeflokaal', 'Walhalla Brouwerij & Proeflokaal', 'Asterweg 2, 1031 HN Amsterdam',
     ['Walhalla Brouwerij & Proeflokaal'], ['jazz']),
    ('greene-room', 'Greene Room', 'Elementenstraat 16, Amsterdam Westpoort',
     ['Greene Room'], ['jazz']),
    ('sloterkerk', 'Sloterkerk', 'Osdorperweg 28, Amsterdam, Nederland',
     ['Sloterkerk'], ['classical']),
    ('likeminds', 'Likeminds', 'Gedempt Hamerkanaal 203, 1021 KP Amsterdam',
     ['Likeminds'], ['theater']),
    ('brakke-grond', 'Brakke Grond', 'Nes 45, 1012 KD Amsterdam',
     ['Brakke Grond'], ['theater']),
    ('schellingwouderkerk', 'Schellingwouderkerk', None,
     ['Schellingwouderkerk'], ['theater']),
    ('levenslang', 'Levenslang', 'H.J.E. Wenckebachweg 48, 1096AN, Amsterdam',
     ['Levenslang'], ['club']),
    ('cultureel-cafe-bacchus', 'Cultureel Café Bacchus (Aalsmeer)', 'Gerberastraat 4, 1431 SG Aalsmeer',
     ['Cultureel Café Bacchus'], ['jazz']),
    ('van-puffelen', 'Van Puffelen', 'Prinsengracht 375',
     ['Van Puffelen'], ['jazz']),
    ('elsas-cafe', "Elsa's Café", 'Middenweg 73, 1098 AE Amsterdam',
     ["Elsa's Café"], ['jazz']),
    ('oedipus-brewing', 'Oedipus Brewing', 'Schaafstraat 21, 1021 KD Amsterdam',
     ['Oedipus Brewing'], ['jazz']),
    ('societeit-de-kring', 'Sociëteit de Kring', 'Kleine-Gartmanplantsoen 7-9, 1017 RP Amsterdam',
     ['Sociëteit de Kring'], ['jazz']),
    ('laurierstraat-72', 'Laurierstraat 72', 'Laurierstraat 72',
     ['Laurierstraat 72'], ['jazz']),
    ('zuiderkerk', 'Zuiderkerk', 'Zuiderkerkhof 72, 1011 WB Amsterdam',
     ['Zuiderkerk'], ['classical']),
    ('concertgemaal', 'Concertgemaal', 'Landsmeerderdijk 213, 1035 PV Amsterdam',
     ['Concertgemaal'], ['classical']),
    ('vermaning', 'Vermaning (Zaandam)', 'Westzijde 80, Zaandam',
     ['Vermaning'], ['classical']),
    ('singelkerk', 'Singelkerk', 'Singel 452, Amsterdam, Noord-Holland, 1017 AW, Nederland',
     ['Singelkerk'], ['classical']),
    ('phono-lake', 'Phono Lake', 'Christoffel Plantijngracht 4, 1065 DA Amsterdam, The Netherlands',
     ['Phono Lake'], ['club']),
    ('de-boule-de-boule', 'De Boule De Boule', 'Waterlooplein 6A, 1011 PG Amsterdam',
     ['De Boule De Boule'], ['jazz']),
    ('volkshotel', 'Volkshotel', 'Wibautstraat 150, 1091 GR Amsterdam',
     ['Volkshotel'], ['jazz', 'alternative']),
    ('societeit-ramses-shaffy-huis', 'Sociëteit Ramses Shaffy Huis', 'Piet Heinkade 231, 1019 HM Amsterdam',
     ['Sociëteit Ramses Shaffy Huis'], ['jazz']),
    ('het-molenpad', 'Het Molenpad', 'Prinsengracht 653',
     ['Het Molenpad'], ['jazz']),
    ('podium-genieten', 'Podium Genieten', 'Oranje Vrijstaatplein 2, 1093 NG Amsterdam',
     ['Podium Genieten'], ['jazz']),
    ('breugem-meeting-point', 'Breugem Meeting Point', 'Nieuwe Hemweg 2, 1013 BG Amsterdam',
     ['Breugem Meeting Point'], ['jazz']),
    ('portugese-synagoge', 'Portugese Synagoge', 'Mr. Visserplein 3, 1011 RD Amsterdam',
     ['Portugese Synagoge'], ['classical']),
    ('het-badhuistheater', 'Het Badhuistheater', 'Boerhaaveplein 28, 1091 AT Amsterdam',
     ['Het Badhuistheater'], ['theater']),
    ('de-cameleon', 'De Cameleon', 'Derde Kostverlorenkade 35, 1054 TS Amsterdam',
     ['De Cameleon'], ['theater']),
    ('san-francisco', 'San Francisco', 'Zeedijk 40, Amsterdam, Netherlands 1012 AZ',
     ['San Francisco'], ['club']),
    ('oba-javaplein', 'OBA Javaplein', 'Javaplein 2, 1094 HW, Amsterdam',
     ['OBA Javaplein'], ['jazz']),
    ('hans-brinker-bar', 'Hans Brinker Bar', 'Kerkstraat 136',
     ['Hans Brinker Bar'], ['jazz']),
    ('jazzcafe-nieuwemeer', 'Jazzcafé NieuweMeer (Aalsmeer)', 'Stommeerweg 2, Aalsmeer',
     ['Jazzcafé NieuweMeer Aalsmeer'], ['jazz']),
    ('a-beautiful-mess', 'A Beautiful Mess', 'Oosterdokskade 227, 1011 DL Amsterdam',
     ['A Beautiful Mess'], ['jazz']),
    ('vreugdehof', 'Vreugdehof', 'De Klencke 111, 1083 HH Amsterdam Buitenveldert',
     ['Vreugdehof, Amsterdam'], ['jazz']),
    ('a-lab', 'A Lab', 'Overhoeksplein 2, 1031KS',
     ['A Lab'], ['jazz', 'alternative']),
    ('elthetokerk', 'Elthetokerk', 'Javastraat 118, 1094 HP, Amsterdam',
     ['Elthethokerk'], ['jazz']),
    ('gamelanhuis', 'Gamelanhuis', 'Veemkade 578, 1019 BL Amsterdam',
     ['Gamelanhuis'], ['classical']),
    ('huis-van-de-wijk-buitenveldert', 'Huis van de Wijk Buitenveldert', 'A.J. Ernststraat 112 , 1082 LP Amsterdam',
     ['Huis van de Wijk Buitenveldert'], ['classical']),
    ('plein-van-siena', 'Plein van Siena', 'Rijnstraat 109hs, 1079 HA Amsterdam',
     ['Plein van Siena'], ['classical']),
    ('embassy-of-the-free-mind', 'Embassy of the Free Mind', 'Keizersgracht 123, 1015 CJ Amsterdam',
     ['Embassy of the Free Mind'], ['classical']),
    ('uilenburgersjoel', 'Uilenburgersjoel', 'Nieuwe Uilenburgerstraat 91, 1011 LM Amsterdam',
     ['Uilenburgersjoel'], ['classical']),
    ('openbare-bibliotheek-amsterdam', 'Openbare Bibliotheek Amsterdam', 'Oosterdokskade 143, 1011 DK Amsterdam',
     ['Openbare Bibliotheek Amsterdam'], ['classical']),
    ('oba-de-hallen', 'OBA de Hallen', 'Hannie Dankbaarpassage 10, 1053 RT Amsterdam',
     ['OBA de Hallen'], ['classical']),
    ('ec-o', 'EC-O', 'Windroosplein 75, 1018 ZZ Amsterdam',
     ['EC-O'], ['classical']),
    ('cafe-checkpoint-charlie', 'Cafe Checkpoint Charlie', 'Nassaukade 48, 1052 CM Amsterdam',
     ['Cafe Checkpoint Charlie'], ['theater']),
    ('bijlmer-parktheater', 'Bijlmer Parktheater', 'Anton de Komplein 240, 1102 DR Amsterdam',
     ['Bijlmer Parktheater'], ['theater']),
    ('cinetol', 'Cinetol', 'Cinetol Tolstraat 182 1074 VM Amsterdam',
     ['Cinetol'], ['pop']),
    ('dick-dick', 'Dick & Dick', 'Gedempt Hamerkanaal 36',
     ['Dick & Dick'], ['club']),
    # Frascati's feed lists its café separately; same building.
    ('het-verbond', 'Het Verbond', 'Nes 71, 1012 KD Amsterdam',
     ['Het Verbond', 'Het Verbond - Café'], ['theater']),
    # --- alternative calendar only (squats, DIY spaces) ---
    ('nieuwland', 'NieuwLand', 'Pieter Nieuwlandstraat 93, Amsterdam',
     ['NieuwLand'], ['alternative']),
    ('ot301', 'OT301', 'Overtoom 301, Amsterdam',
     ['OT301'], ['alternative']),
    ('joes-garage', "Joe's Garage", 'Pretoriusstraat 43, Amsterdam',
     ["Joe's Garage"], ['alternative']),
    # LAG (an anarchist group) meets at Bollox: same address.
    ('infokafee-bollox', 'Infokafee Bollox', 'Eerste Schinkelstraat 14-16, Amsterdam',
     ['Infokafee Bollox', 'LAG'], ['alternative']),
    ('mkz', 'MKZ', 'Eerste Schinkelstraat 16, Amsterdam',
     ['MKZ'], ['alternative']),
    ('vrankrijk', 'Vrankrijk', 'Spuistraat 216, Amsterdam',
     ['Vrankrijk'], ['alternative']),
    ('rapenburg-51', 'Rapenburg 51', 'Rapenburg 51, Amsterdam',
     ['Rapenburg 51'], ['alternative']),
    ('ruigoord', 'Ruigoord', 'Ruigoord 76, 1047 HH Amsterdam',
     ['Ruigoord'], ['alternative']),
    ('molli-chaoot', 'Molli Chaoot', 'Van Ostadestraat 55hs, Amsterdam',
     ['Molli Chaoot'], ['alternative']),
    # Het Groene Veld has two sites; Stichting Malak and Het Sociaal Centrum
    # are tenants at the Scheurleerweg one.
    ('het-groene-veld', 'Het Groene Veld', 'G.J. Scheurleerweg 212c, Amsterdam',
     ['Het Groene Veld', 'Stichting Malak', 'Het Sociaal Centrum'], ['alternative']),
    ('het-groene-veld-machinegebouw', 'Het Groene Veld (Machinegebouw)', 'Buikslotermeerdijk 95, Amsterdam',
     ['Het Groene Veld (Machinegebouw)', 'Het Groene Veld / ADM Noord'], ['alternative']),
    ('droog', 'Droog', 'Staalstraat 7B, Amsterdam',
     ['Droog'], ['alternative']),
    ('mediamatic', 'Mediamatic Biotoop', 'Dijksgracht 6, 1019 BS Amsterdam',
     ['Mediamatic Biotoop'], ['alternative']),
    ('vondelbunker', 'Vondelbunker', 'Vondelpark 8a, Amsterdam',
     ['Vondelbunker'], ['alternative']),
    ('de-verdieping', 'De Verdieping (bij Kaboem)', 'Anna Spenglerstraat 83, Amsterdam',
     ['De Verdieping (bij Kaboem)'], ['alternative']),
    ('kaskantine', 'Kaskantine', 'Handbalstraat 1, 1062 XA Amsterdam',
     ['Kaskantine'], ['alternative']),
    ('spuistraat-5', 'Spuistraat 5', 'Spuistraat 5, Amsterdam',
     ['Spuistraat 5'], ['alternative']),
    ('huis-vrederiks', 'Huis Vrederiks', 'Frederiksplein 52, Amsterdam',
     ['Huis Vrederiks'], ['alternative']),
    ('technologia-incognita', 'Technologia Incognita', 'Louwesweg, Amsterdam',
     ['Technologia Incognita'], ['alternative']),
    ('einde-van-de-wereld', 'Einde van de Wereld', 'Javakade 61, 1019 BK Amsterdam',
     ['Einde van de Wereld'], ['alternative']),
    # One complex, listed by squatradar and Plantage Dok's own feed.
    ('plantage-dok', 'Plantage Dok', 'Plantage Doklaan 8-12, 1018 CM Amsterdam',
     ['Plantage Dok', 'Dokhuis Galerie', 'Dokhuis', 'Plantage Doklaan 8-12'], ['alternative']),
    ('fc-kraak', 'FC Kraak', 'Radioweg 96, Amsterdam',
     ['FC Kraak'], ['alternative']),
    ('w139', 'W139', 'Warmoesstraat 139, 1012 JB Amsterdam',
     ['W139'], ['alternative']),
    ('parknest', 'Parknest', 'Flevopark 15, Amsterdam',
     ['Parknest'], ['alternative']),
    ('rozenstraat', 'Rozenstraat', 'Rozenstraat 59, 1016 NN Amsterdam',
     ['Rozenstraat'], ['alternative']),
    ('budapest', 'Budapest', 'Pesthuislaan, Amsterdam',
     ['Budapest'], ['alternative']),
    ('takland', 'Takland', 'Taksteeg 6, Amsterdam',
     ['Takland'], ['alternative']),
    ('grond', 'GROND', 'Bijdorpstraat 1, 1096 AP Amsterdam',
     ['GROND'], ['alternative']),
    ('framer-framed', 'Framer Framed', 'Oranje-Vrijstaatkade 71, 1093 KS Amsterdam',
     ['Framer Framed'], ['alternative']),
    ('nieuw-en-meer', 'Nieuw en Meer', 'Oude Haagseweg 53A1, 1066 BV Amsterdam',
     ['Nieuw en Meer'], ['alternative']),
    ('astarotheatro', 'AstaroTheatro', 'Sint Jansstraat 37, Amsterdam',
     ['AstaroTheatro'], ['alternative']),
    ('treehouse-ndsm', 'Treehouse NDSM', 'T.T. Neveritaweg 55-57, 1033 WB Amsterdam',
     ['Treehouse NDSM'], ['alternative']),
]


def _venue_key(name: str) -> str:
    """Normalize a jazzin venue name for alias matching: case- and
    whitespace-insensitive ("ZOjazz Stage", "ZOJazzstage " → "zojazzstage")."""
    return re.sub(r"\s+", "", name).casefold()


VENUE_BY_KEY: dict[str, str] = {
    _venue_key(alias): slug for slug, _name, _addr, aliases, _cats in VENUES for alias in aliases
}
VENUE_CATEGORIES: dict[str, set[str]] = {slug: set(cats) for slug, *_rest, cats in VENUES}

# DENYLIST: jazzin venue names (matched via _venue_key) that never become
# venues, with why. Their events are dropped.
DENIED: dict[str, str] = {
    # not venues
    "Amsterdam": "bare city name, no venue (address ', Amsterdam')",
    "Buikslotermeerplein": "street corner of the weekly 'Vlaggen voor Palestina' vigil",
    "Op de brug": "street corner of the weekly 'Vlaggen voor Palestina' vigil",
    "Jan van Galenstraat A10 snelweg": "street corner of the weekly 'Vlaggen voor Palestina' vigil",
    "Fossil Free Culture NL": "an organisation, not a venue (address just 'Overtoom, Amsterdam')",
    "Grote Zaal": "bare hall name (Comedytrain, Westergas) from the junk toomler feed",
    "Kleine Zaal": "bare hall name (Comedytrain, Westergas) from the junk toomler feed",
    # closed
    "Bar Bario": "closed; its feed re-dates past events into next year",
    # owned by a dedicated scraper (filmhuis_cavia.py, venue filmhuis-cavia)
    "Filmhuis Cavia": "own scraper: filmhuis_cavia.py",
    "Nassaukerk": "Filmhuis Cavia's one-off screening there; own scraper: filmhuis_cavia.py",
    # outside the Amsterdam area (the cva feed tours the Conservatorium's students)
    "Stadsgehoorzaal Leiden": "Leiden — outside the Amsterdam area",
    "TivoliVredenburg": "Utrecht — outside the Amsterdam area",
    "Theater Het Klooster Woerden": "Woerden — outside the Amsterdam area",
    "Papagenohuis": "Laren — outside the Amsterdam area",
    "De Kulturele Raad": "Hillegom — outside the Amsterdam area",
}
DENIED_KEYS: frozenset[str] = frozenset(_venue_key(n) for n in DENIED)

# Upstream feeds (the API's `source` field) dropped whole, with why.
DENIED_FEEDS: dict[str, str] = {
    "toomler": "Comedytrain's halls (Westergas): junk titles like '20:30 uur'",
}


def slugify(name: str) -> str:
    """A discovered venue's slug: ascii, lowercase, hyphens; quotes dropped
    ("Joe's Garage" → "joes-garage", "Café Czaar" → "cafe-czaar")."""
    ascii_ = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    ascii_ = re.sub("['\"`]", "", ascii_.casefold())
    return re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")


def _address(raw: str | None) -> str | None:
    """jazzin's address, whitespace-collapsed; None when it's just the city."""
    text = re.sub(r"\s+", " ", raw or "").strip()
    return None if text.strip(" ,").casefold() in ("", "amsterdam") else text


# --- price -----------------------------------------------------------------

# An amount with optional decimals: "12", "12.5", "12,50", "15.00".
_AMOUNT_RE = re.compile(r"\d+(?:[.,]\d+)?")
_CURRENCY_PREFIX_RE = re.compile(r"^(?:€|EUR\b)\s*", re.IGNORECASE)
_FREE = {"free", "gratis", "0", "€0", "€ 0"}
_SOLD_OUT = {"s.o.", "sold out", "uitverkocht"}


def _fmt_amount(x: float) -> str:
    """12.0 → "12", 12.5 → "12,50" (Dutch decimal comma, like "8,50€")."""
    return str(int(x)) if x == int(x) else f"{x:.2f}".replace(".", ",")


def parse_price(raw: str) -> str | None:
    """jazzin price free text → the price convention.

    "" / bare "€" → None; "free" / "0" → "free"; "s.o." → "sold-out"; amounts
    ("€13", "EUR 15.00", "€12.5–€25", "6 / 12.5") → "13€" etc., with the shared
    2× rule: a range only when the high price is at least twice the low, else
    the highest. Text with no amount ("donatie") passes through, minus a leading
    "€"/"EUR" marker."""
    text = raw.strip()
    low = text.casefold()
    if not text or text == "€":
        return None
    if low in _FREE:
        return "free"
    # Exact markers, plus compound statuses like "uitverkocht/nietbeschikbaar".
    if low in _SOLD_OUT or low.startswith(("uitverkocht", "sold out")):
        return "sold-out"
    amounts = [float(a.replace(",", ".")) for a in _AMOUNT_RE.findall(text)]
    if not amounts:
        # Some feeds prefix free text with a currency marker ("€Sliding scale
        # donation", a bare "EUR "): drop it.
        text = _CURRENCY_PREFIX_RE.sub("", text).strip()
        return text or None
    lo, hi = min(amounts), max(amounts)
    if hi <= 0:
        return "free"
    if lo == hi or hi < 2 * lo:
        return f"{_fmt_amount(hi)}€"
    return f"{_fmt_amount(lo)}–{_fmt_amount(hi)}€"


# --- events ----------------------------------------------------------------

def _parse_time(raw: str | None) -> dt.time | None:
    if not raw:
        return None
    try:
        return dt.time.fromisoformat(raw)
    except ValueError:
        return None


# Status markers some upstream feeds put in the title.
_SOLD_OUT_MARK = re.compile(r"\s*[\[(](?:sold ?out|uitverkocht)[\])]", re.IGNORECASE)
_CANCELED_MARK = re.compile(r"[\[(](?:canceled|cancelled|afgelast|geannuleerd)[\])]", re.IGNORECASE)


def _norm_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().casefold()


def occurrence_key(start_date: dt.date, start_time: dt.time | None, title: str) -> str:
    """Content-derived external_id: jazzin's maintainer re-scrapes everything
    nightly, so its numeric ids are not stable across runs. Date + start time
    + normalized title is (the occurrence merge below makes it unique per
    venue within a batch)."""
    hhmm = start_time.strftime("%H%M") if start_time else "none"
    raw = f"{start_date.isoformat()}T{hhmm}|{_norm_title(title)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def resolve_venue(name: str) -> str | None:
    """The venue slug a jazzin venue name maps to: an override's (alias
    match), else the discovered slug; None when the name is denied or yields
    no slug."""
    key = _venue_key(name)
    if key in VENUE_BY_KEY:
        return VENUE_BY_KEY[key]
    if not key or key in DENIED_KEYS:
        return None
    return slugify(name) or None


def parse_events(
    items: list[tuple[str, dict]],
) -> tuple[list[ScrapedEvent], list[VenueDefinition], set[str]]:
    """Map (category slug, API event object) pairs to ScrapedEvents. Pure:
    JSON in, events out.

    Returns (events, discovered venues, denied names). Opt-out: an event at a
    venue name that matches no override alias and isn't DENIED (nor from a
    DENIED_FEEDS feed) goes to a discovered venue — see discover_venues.

    jazzin repeats occurrences under several ids — within a calendar
    (Muziekgebouw lists a concert up to 5×) and across calendars (a
    Muziekgebouw gig in both jazz and classical). Occurrences are merged on
    (venue, date, time, normalized title) — the content-derived external_id,
    see occurrence_key — keeping the first-listed (lowest id) item's fields
    and the union of the calendars' categories."""
    by_key: dict[tuple, ScrapedEvent] = {}
    denied: set[str] = set()
    # discovered slug → raw names / addresses seen for it
    names: dict[str, Counter[str]] = {}
    addresses: dict[str, Counter[str]] = {}
    for category, item in sorted(items, key=lambda ci: ci[1].get("id") or 0):
        venue_name = re.sub(r"\s+", " ", item.get("venue") or "").strip()
        venue_slug = None if item.get("source") in DENIED_FEEDS else resolve_venue(venue_name)
        if venue_slug is None:
            denied.add(venue_name)
            continue
        title = (item.get("title") or "").strip()
        if not title or not item.get("date") or _CANCELED_MARK.search(title):
            continue
        sold_out = bool(_SOLD_OUT_MARK.search(title))
        title = _SOLD_OUT_MARK.sub("", title).strip()
        try:
            start_date = dt.date.fromisoformat(item["date"])
        except ValueError:
            continue
        start_time = _parse_time(item.get("time"))

        if venue_slug not in VENUE_CATEGORIES:
            names.setdefault(venue_slug, Counter())[venue_name] += 1
            if addr := _address(item.get("address")):
                addresses.setdefault(venue_slug, Counter())[addr] += 1

        external_id = occurrence_key(start_date, start_time, title)
        key = (venue_slug, external_id)
        if key in by_key:
            ev = by_key[key]
            if category not in ev.category_slugs:
                ev.category_slugs.append(category)
            continue
        by_key[key] = ScrapedEvent(
            title=title,
            start_date=start_date,
            start_time=start_time,
            # strip("'") — the w139 feed leaves a stray trailing quote.
            source_url=(item.get("site") or "").strip().strip("'\"") or FALLBACK_URL,
            category_slugs=[category],
            price="sold-out" if sold_out else parse_price(item.get("price") or ""),
            external_id=external_id,
            venue_slug=venue_slug,
        )
    events = list(by_key.values())
    return events, discover_venues(events, names, addresses), denied


def discover_venues(
    events: list[ScrapedEvent],
    names: dict[str, Counter[str]],
    addresses: dict[str, Counter[str]],
) -> list[VenueDefinition]:
    """One VenueDefinition per discovered slug: jazzin's most common name and
    address for it (None when only "Amsterdam"), city amsterdam, and the
    categories of the calendars its events appear in, each a whitelisted list
    membership (the same shape as the overrides)."""
    cats: dict[str, set[str]] = {}
    for ev in events:
        if ev.venue_slug in names:
            cats.setdefault(ev.venue_slug, set()).update(ev.category_slugs)
    order = list(CALENDARS.values())
    venues = []
    for slug in sorted(cats):
        cs = sorted(cats[slug], key=order.index)
        addr = addresses.get(slug)
        venues.append(_venue_definition(
            slug, names[slug].most_common(1)[0][0],
            addr.most_common(1)[0][0] if addr else None, cs))
    return venues


def _venue_definition(slug: str, name: str, address: str | None, cats: list[str]) -> VenueDefinition:
    return VenueDefinition(
        slug=slug,
        name=name,
        city_slug=CITY_SLUG,
        address=address,
        category_slugs=cats,
        list_memberships=[ListMembership(list_slug=c, whitelist_category_slug=c) for c in cats],
    )


def unlisted_categories(events: list[ScrapedEvent]) -> set[tuple[str, str]]:
    """(override venue, category) pairs the feed now has but VENUES doesn't
    list — those events are stored but no list shows them until the venue's
    row is updated. (Discovered venues gain categories automatically.)"""
    return {
        (ev.venue_slug, c)
        for ev in events
        if ev.venue_slug in VENUE_CATEGORIES
        for c in ev.category_slugs
        if c not in VENUE_CATEGORIES[ev.venue_slug]
    }


def fetch_items() -> list[tuple[str, dict]]:
    """Every upcoming event of every calendar, paging by offset until a short
    page."""
    items: list[tuple[str, dict]] = []
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for calendar, category in CALENDARS.items():
            for page in range(MAX_PAGES):
                resp = client.get(
                    API_URL,
                    params={"calendar": calendar, "archive": "false", "offset": page * PAGE_SIZE},
                )
                resp.raise_for_status()
                batch = resp.json()
                items.extend((category, item) for item in batch)
                if len(batch) < PAGE_SIZE:
                    break
    return items


class JazzinAmsterdamScraper:
    """Opt-out: also implements scrapers.base.DiscoversVenues."""

    def __init__(self) -> None:
        self._discovered: list[VenueDefinition] = []

    def scrape(self) -> list[ScrapedEvent]:
        events, self._discovered, denied = parse_events(fetch_items())
        if denied:
            logger.info("jazzin-amsterdam: dropped events at %d denied venue names", len(denied))
            logger.debug("jazzin-amsterdam: denied venue names: %s", ", ".join(sorted(denied)))
        if missing := unlisted_categories(events):
            logger.warning(
                "jazzin-amsterdam: venues with events in categories they aren't listed for: %s",
                ", ".join(f"{v}/{c}" for v, c in sorted(missing)),
            )
        return events

    def discovered_venues(self) -> list[VenueDefinition]:
        return list(self._discovered)


register_source(
    scraper=JazzinAmsterdamScraper(),
    source=SourceDefinition(
        slug=SOURCE_SLUG,
        name="jazzin.amsterdam",
        # The overrides only; discovered venues are created at run time.
        venues=[
            _venue_definition(slug, name, address, cats)
            for slug, name, address, _aliases, cats in VENUES
        ],
    ),
)
