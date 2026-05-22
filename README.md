# Where to watch the World Cup in New York City

Pick a 2026 World Cup nation and the map shades the NYC neighborhoods densest with
people born in that country, then pins restaurants and bars of that cuisine located
right where the community lives — good places to watch the match with a crowd of
fellow supporters.

Interactive map + infographic. Static HTML/JS frontend (no build step); Python
data-bake scripts. Uses the Vital City design system tokens/fonts for polish.

## Live structure

- `docs/index.html` — the whole app (Leaflet, scoped under `.wc-root`)
- `docs/methodology.md` — full methodology + caveats
- `docs/data/` — generated payloads served to the frontend
- `config/teams.json` — the 48-team field (editable, TBD-aware)
- `config/nation_mapping.json` — nation → ACS B05006 code(s) + DOHMH cuisine(s) (editable)

GitHub Pages serves from `/docs`.

## Rebuilding the data

Run the scripts in order from the project root:

```bash
python3 scripts/00_fetch_pumas.py                    # shoreline-clipped PUMA boundaries + names (no key)
python3 scripts/01_fetch_acs_b05006.py  $CENSUS_KEY  # ACS country-of-birth at PUMA level
python3 scripts/02_pull_dohmh.py                     # DOHMH restaurants by cuisine (no key)
python3 scripts/03_colocate.py                       # rank neighborhoods + co-locate venues (no key)
python3 scripts/05_build_outputs.py                  # assemble per-team JSON + manifest (no key)
```

- **Census key** (free): https://api.census.gov/data/key_signup.html — passed as an
  argument (or env var `CENSUS_API_KEY`) and never written into any output.
- **Ratings/price are intentionally omitted.** Every provider that carries restaurant
  ratings (Yelp, Google, Foursquare) requires payment and/or forbids re-hosting their
  data in a static map. `scripts/04_enrich_foursquare.py` exists for the day a free,
  terms-compliant source appears, but is **not part of the standard build**.

To resolve a TBD qualifier or change the field: edit `config/teams.json` (and
`config/nation_mapping.json` if it's a new nation), then re-run `03`–`05`.

## Embedding in Ghost

The page is embeddable. Add `?embed=1` to strip the fullscreen chrome; it posts its
height to the parent so the host iframe can resize:

```html
<iframe src="https://<host>/world-cup-nyc/index.html?embed=1"
        style="width:100%;border:0;" height="680" title="Where to watch the World Cup in NYC"></iframe>
<script>
addEventListener('message', e => {
  if (e.data && e.data.type === 'wc-embed-height') {
    document.querySelector('iframe[src*="world-cup-nyc"]').height = e.data.height;
  }
});
</script>
```

## Data sources

- U.S. Census Bureau ACS 5-year, table B05006 (place of birth for the foreign-born), at PUMA geography
- NYC Dept. of City Planning shoreline-clipped 2020 PUMA boundaries (NYC Open Data `pikk-p9nv`); names from Census TIGERweb
- NYC DOHMH Restaurant Inspection Results (NYC Open Data `43nn-pn8j`)

See [docs/methodology.md](docs/methodology.md) for assumptions, margins of error, and limitations.
