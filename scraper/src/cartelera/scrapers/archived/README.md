# Archived scrapers

Scrapers that are written and working but intentionally **not registered** —
they are not imported by `run.py`/`seed.py`, so their `register(...)` call never
runs and they don't appear in the `REGISTRY` or the seed. Parked here so the work
isn't lost and can be revived by moving the module back up to
`cartelera/scrapers/` and adding the import line.

This directory is **not a package** (no `__init__.py`) and is **not collected by
pytest** (`testpaths = ["tests"]`).

## casa_batllo

Casa Batlló "Magical Nights" rooftop concerts. The scraper works (80 events,
per-occurrence external_ids, verified live 2026-06-02) but the venue was dropped
from the active set: it's a touristy visit+cava+concert bundle aimed at visitors,
not the local audience Cartelera serves, and its 2026 lineup is generic
soul/funk/disco/world live music with no classical programming (it fell back to
`jazz`). Revive only if we decide to cover tourist-oriented live music.
