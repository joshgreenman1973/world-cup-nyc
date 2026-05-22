# Methodology — Where to watch the World Cup in New York City

## What this is

Pick a 2026 World Cup nation and the map does two things:

1. **Shades New York City neighborhoods** by how many residents were born in that country.
2. **Pins restaurants and bars** of that nation's cuisine that sit *inside* the neighborhoods densest with that community.

It is meant to help you find a neighborhood with a real crowd of fellow supporters and a place of that cuisine to eat and watch.

## What this is NOT

This is a heuristic, not a listings guide. It does **not** know which bars actually screen matches, have sound on, or take reservations. It infers "good place to watch your team" from two proxies — where a nation's New Yorkers live, and where that cuisine clusters. Call ahead before you go.

## Geography: why PUMAs (and what that costs us)

Country-of-birth detail comes from the U.S. Census Bureau's American Community Survey (ACS), table **B05006** ("place of birth for the foreign-born population").

The honest constraint: for any single country, these estimates carry **large margins of error** at the census-tract level, and still-substantial error even when tracts are aggregated to neighborhoods (NTAs). For many nations the margin of error would exceed the estimate itself.

So we use **Public Use Microdata Areas (PUMAs)** — the smallest geography for which the Census Bureau *directly tabulates* B05006 (no tract-summing, so no inflated error). New York City has **55 PUMAs**, and they carry official neighborhood names ("Jackson Heights & East Elmhurst", "Bensonhurst & Bath Beach", "Washington Heights & Inwood").

- **The benefit:** statistically defensible numbers with human-readable neighborhood labels.
- **The cost:** PUMAs are coarse (~100,000–200,000 residents each). A PUMA named "Jackson Heights & East Elmhurst" lumps more than one neighborhood together. We show the official name and a per-neighborhood reliability dot.

**Reliability dots** (shown on hover) come from the coefficient of variation, derived from the published margin of error (a 90% confidence interval, so the standard error is the margin divided by 1.645):

- Green / **high**: coefficient of variation under 15%
- Orange / **moderate**: 15% to 30%
- Magenta / **low**: 30% or more

When a nation's residents are summed across multiple ACS codes, the combined margin of error is the square root of the sum of the squared margins.

## "Place of birth" is not ancestry

ACS B05006 counts the **foreign-born** — people living in NYC who were born abroad. That means:

- U.S.-born children and grandchildren of immigrants are **not** counted. A neighborhood full of second-generation Italian-Americans may show few Italy-*born* residents.
- Undocumented residents are undercounted.
- Figures are 5-year rolling averages (2019–2023), so they smooth over recent change.
- A few nations are not broken out separately and fall into regional "Other" buckets (Paraguay, Tunisia, Qatar, New Zealand among World Cup teams). Those teams have **no neighborhood shading** and are flagged "limited data."
- "Korea" is not split into North and South; in practice nearly all Korea-born New Yorkers are from South Korea. The United Kingdom is reported as England and Scotland separately, with Wales and Northern Ireland folded into a combined code.

## Restaurants and bars

Source: **NYC Department of Health and Mental Hygiene (DOHMH) Restaurant Inspection Results** (NYC Open Data, dataset `43nn-pn8j`), which carries a `cuisine_description` field and a pre-geocoded location for every inspected food-service establishment. One record is kept per establishment (the most recent inspection).

### Cuisine is not nationality

DOHMH's cuisine vocabulary is broad and does not map cleanly to all 48 teams. We curated the mapping by hand (see `data/nation_mapping.json`), and each team carries a caveat where the match is weak:

- Many South American nations share one **"Latin American"** tag; African nations share **"African"**; several Gulf nations share **"Middle Eastern"**. Co-location to the right neighborhood is what makes these specific (a Senegalese spot only surfaces if it's in a Senegalese neighborhood).
- The DOHMH **"Spanish"** tag, in NYC, overwhelmingly means Caribbean/Latino food, not food from Spain — so Spain leans on the narrower "Tapas" tag with a caveat.
- Some nations have **no usable cuisine tag** (Netherlands, Belgium, Switzerland) and show neighborhood shading but no restaurant pins.
- DOHMH covers food-serving establishments. **Pure bars without a food license may be under-represented.**

### Co-location: only spots where the community actually lives

For each nation we rank the 55 PUMAs by that nation's resident count, then take the **densest set** — the top neighborhoods that together hold at least 60% of the nation's NYC residents, capped between 1 and 8 neighborhoods. A restaurant is shown **only if** its cuisine matches the nation **and** its location falls inside that densest set (tested by point-in-polygon against the PUMA boundaries). This is what stops the map from sending you to a great Senegalese restaurant in a neighborhood with no Senegalese community.

### Why there are no ratings or prices

The spots are **not quality-ranked.** We wanted to surface well-rated, affordable places, but every source that carries restaurant ratings and price (Yelp, Google, Foursquare, Tripadvisor) gates that data behind a paid and/or keyed API, and their terms of service prohibit re-hosting or caching that content into a static map like this one. The free, terms-compliant alternatives (OpenStreetMap) carry locations and cuisine but no ratings. Rather than scrape (which violates those terms) or pay, we show the cuisine-matched spots **unranked** — accurate about what we can and can't measure. If a free, compliant ratings source becomes available, it can be layered in later.

## Limitations, in brief

- Coarse PUMA geography; small diasporas are statistically noisy.
- Place of birth ≠ ancestry ≠ who shows up to watch a match.
- Cuisine tags are broad and hand-mapped to nations.
- A current DOHMH inspection record is not proof a place is open today.
- Spots are not ranked by quality or price (see "Why there are no ratings or prices").
- The 48-team field is provisional and must be checked against final qualification.

## Reproducing this

All data is rebuilt by the scripts in `scripts/` (`00`–`03`, then `05`; step `04`, Foursquare enrichment, is present but unused since there is no free, terms-compliant ratings source). Sources: Census ACS API (table B05006 at PUMA geography, requires a free key), NYC City Planning shoreline-clipped PUMA boundaries (`pikk-p9nv`), Census TIGERweb (PUMA names), and NYC Open Data Socrata (`43nn-pn8j`). The nation→code→cuisine mapping lives in `config/nation_mapping.json` and the team field in `config/teams.json` — both editable.
